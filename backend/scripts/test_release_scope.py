"""Regression coverage for store boundaries, using only an in-memory database."""

import asyncio
import os
import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

os.environ["DATABASE_URL"] = "sqlite://"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.api.routes import admin, ble
from app.db.session import Base
from app.models import AdminUser, BillType, BleKey, BleLock, DoorLog, Reservation, Seat, Store, User, Zone


class ReleaseScopeTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.db.add_all([Store(id=1, name="Own"), Store(id=2, name="Other")])
        self.user = User(id=1, openid="scope-test")
        self.manager = AdminUser(id=1, username="manager", password_hash="unused", role="store", store_id=1)
        self.hq = AdminUser(id=2, username="hq", password_hash="unused", role="hq")
        self.db.add_all([self.user, self.manager, self.hq])
        self.seats = {}
        for store_id in (1, 2):
            zone = Zone(store_id=store_id, name="Study")
            self.db.add(zone)
            self.db.flush()
            self.seats[store_id] = [Seat(store_id=store_id, zone_id=zone.id, seat_code=str(n)) for n in (1, 2)]
            self.db.add_all(self.seats[store_id])
            self.db.add(BleLock(id=store_id, store_id=store_id, lock_id=f"mock_{store_id}"))
        self.db.commit()
        self.serial = 0

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def reservation(self, store_id, *, seat_index=0, start=None):
        self.serial += 1
        start = start or datetime.now() + timedelta(days=self.serial)
        row = Reservation(
            order_no=f"scope-{self.serial}", user_id=1, store_id=store_id,
            seat_id=self.seats[store_id][seat_index].id, bill_type=BillType.hourly,
            start_time=start, end_time=start + timedelta(hours=2), pay_status=1, status=0,
        )
        self.db.add(row)
        self.db.flush()
        self.db.add(BleKey(lock_id=store_id, reservation_id=row.id, user_id=1, status=1))
        self.db.commit()
        return row

    def invoke(self, action, actor, row, other=None):
        if action == "seat-options":
            return admin.admin_reservation_seat_options(row.id, actor, self.db)
        if action == "change-seat":
            return admin.admin_change_reservation_seat(
                row.id, admin.AdminChangeSeatRequest(seat_id=self.seats[row.store_id][1].id), actor, self.db
            )
        if action == "swap-seats":
            return admin.admin_swap_reservation_seats(
                row.id, admin.AdminSwapSeatsRequest(other_reservation_id=other.id), actor, self.db
            )
        if action == "remote-unlock":
            # Avoid wall-clock dependence; the fake lock never contacts TTLock.
            with patch("app.services.admin_ops.settings.ttlock_remote_unlock_enabled", True), \
                 patch("app.services.admin_ops.reservation_unlock_allowed", return_value=True):
                return asyncio.run(admin.admin_reservation_remote_unlock(row.id, actor, self.db))
        return admin.admin_reservation_force_checkout(row.id, actor, self.db)

    def test_store_manager_cannot_operate_other_store_reservations(self):
        for action in ("seat-options", "change-seat", "swap-seats", "remote-unlock", "force-checkout"):
            with self.subTest(action=action):
                row = self.reservation(2)
                other = self.reservation(2, seat_index=1, start=row.start_time) if action == "swap-seats" else None
                with self.assertRaises(HTTPException) as error:
                    self.invoke(action, self.manager, row, other)
                self.assertEqual(error.exception.status_code, 403)
                self.db.refresh(row)
                self.assertEqual(row.status, 0)
                self.assertEqual(row.seat_id, self.seats[2][0].id)
        self.assertEqual(self.db.scalars(select(DoorLog)).all(), [])

    def test_swap_rejects_other_store_as_second_reservation(self):
        own, other = self.reservation(1), self.reservation(2)
        with self.assertRaises(HTTPException) as error:
            self.invoke("swap-seats", self.manager, own, other)
        self.assertEqual(error.exception.status_code, 403)

    def assert_workflows_allowed(self, actor, store_id):
        for action in ("seat-options", "change-seat", "swap-seats", "remote-unlock", "force-checkout"):
            with self.subTest(action=action):
                row = self.reservation(store_id)
                other = self.reservation(store_id, seat_index=1, start=row.start_time) if action == "swap-seats" else None
                response = self.invoke(action, actor, row, other)
                self.assertEqual(response.code, 0)
                self.db.refresh(row)
                if action in ("change-seat", "swap-seats"):
                    self.assertEqual(row.seat_id, self.seats[store_id][1].id)
                elif action == "force-checkout":
                    self.assertEqual(row.status, 2)
                elif action == "remote-unlock":
                    log = self.db.scalar(select(DoorLog).where(DoorLog.reservation_id == row.id))
                    self.assertIsNotNone(log)
                    self.assertEqual(log.lock_id, store_id)

    def test_own_store_workflows_remain_available(self):
        self.assert_workflows_allowed(self.manager, 1)

    def test_hq_can_operate_other_store(self):
        self.assert_workflows_allowed(self.hq, 2)

    def door_logs(self, actor, lock_id, store_id=None):
        return ble.admin_list_door_logs(
            lock_id=lock_id, store_id=store_id, result=None, date_from=None, date_to=None,
            page=1, page_size=20, admin=actor, db=self.db,
        ).data

    def test_lock_filter_does_not_bypass_store_boundary(self):
        self.db.add_all([DoorLog(lock_id=1), DoorLog(lock_id=2)])
        self.db.commit()
        self.assertEqual(self.door_logs(self.manager, 2).total, 0)
        own = self.door_logs(self.manager, 1)
        self.assertEqual(own.total, 1)
        self.assertEqual(own.items[0]["lock_id"], 1)
        self.assertEqual(self.door_logs(self.hq, 2).total, 1)
        self.assertEqual(self.door_logs(self.hq, 2, store_id=1).total, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
