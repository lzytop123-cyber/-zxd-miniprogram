"""月卡请假/停卡（3 次限额 + 方案 A 顺延排座 + 释放座位 + 撤销）单元测试。"""

from __future__ import annotations

import os
import sys
import unittest
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import (
    AdminUser,
    Base,
    BillType,
    PayType,
    Reservation,
    Seat,
    Store,
    User,
    Zone,
)
from app.services.business import find_seat_conflict
from app.services.reservation_leave import (
    cancel_or_resume_monthly_leave,
    create_monthly_leave,
    is_reservation_on_leave,
    preview_monthly_leave,
)


class MonthlyLeaveTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()

        self.store = Store(name="测试门店", address="测试路1号", status=1)
        self.db.add(self.store)
        self.db.flush()

        self.zone = Zone(store_id=self.store.id, name="沉浸区")
        self.db.add(self.zone)
        self.db.flush()

        self.seat1 = Seat(store_id=self.store.id, zone_id=self.zone.id, seat_code="1", status=1)
        self.seat2 = Seat(store_id=self.store.id, zone_id=self.zone.id, seat_code="2", status=1)
        self.db.add_all([self.seat1, self.seat2])

        self.user = User(openid="u_leave_1", nickname="请假同学", phone="13800001111")
        self.user2 = User(openid="u_leave_2", nickname="其他同学", phone="13800002222")
        self.admin = AdminUser(username="mgr", password_hash="x", role="hq")
        self.db.add_all([self.user, self.user2, self.admin])
        self.db.flush()

        now = datetime.now().replace(hour=9, minute=0, second=0, microsecond=0)
        self.start = now
        self.end = now + timedelta(days=30)
        self.res = Reservation(
            order_no="RES-MONTHLY-1",
            user_id=self.user.id,
            store_id=self.store.id,
            seat_id=self.seat1.id,
            bill_type=BillType.monthly,
            start_time=self.start,
            end_time=self.end,
            final_price=Decimal("399.00"),
            pay_type=PayType.wechat,
            pay_status=1,
            status=1,
        )
        self.db.add(self.res)
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_leave_releases_seat_extends_end_time_and_enforces_3_limit(self):
        d1 = (self.start + timedelta(days=2)).date()
        d2 = (self.start + timedelta(days=3)).date()

        # 第 1 次请假（2天）
        r1 = create_monthly_leave(self.db, self.res, d1, d2, self.admin, reason="回家")
        self.assertEqual(r1["used_count"], 1)
        self.assertEqual(self.res.end_time, self.end + timedelta(days=2))

        # 请假期间原座位应已释放（无冲突）
        conflict_during_leave = find_seat_conflict(
            self.db,
            self.seat1.id,
            datetime.combine(d1, datetime.min.time()) + timedelta(hours=10),
            datetime.combine(d1, datetime.min.time()) + timedelta(hours=14),
        )
        self.assertIsNone(conflict_during_leave)

        # 非请假日期原座位仍占用
        non_leave_day = (self.start + timedelta(days=4)).date()
        conflict_normal = find_seat_conflict(
            self.db,
            self.seat1.id,
            datetime.combine(non_leave_day, datetime.min.time()) + timedelta(hours=10),
            datetime.combine(non_leave_day, datetime.min.time()) + timedelta(hours=14),
        )
        self.assertIsNotNone(conflict_normal)

        # 请假当天 is_reservation_on_leave 命中
        self.assertIsNotNone(is_reservation_on_leave(self.db, self.res.id, datetime.combine(d1, datetime.min.time())))

        # 第 2、3 次请假
        d3 = (self.start + timedelta(days=5)).date()
        d4 = (self.start + timedelta(days=7)).date()
        create_monthly_leave(self.db, self.res, d3, d3, self.admin)
        create_monthly_leave(self.db, self.res, d4, d4, self.admin)
        self.assertEqual(self.res.end_time, self.end + timedelta(days=4))

        # 第 4 次请假必须被拦截
        d5 = (self.start + timedelta(days=9)).date()
        with self.assertRaises(HTTPException) as ctx:
            create_monthly_leave(self.db, self.res, d5, d5, self.admin)
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("3 次", ctx.exception.detail)

    def test_extension_conflict_allows_alternative_seat(self):
        # 有人预约了原座位的顺延时段
        blocker = Reservation(
            order_no="RES-BLOCKER",
            user_id=self.user2.id,
            store_id=self.store.id,
            seat_id=self.seat1.id,
            bill_type=BillType.daily,
            start_time=self.end + timedelta(hours=1),
            end_time=self.end + timedelta(days=2),
            final_price=Decimal("39.00"),
            pay_type=PayType.wechat,
            pay_status=1,
            status=0,
        )
        self.db.add(blocker)
        self.db.commit()

        d1 = (self.start + timedelta(days=2)).date()
        d2 = (self.start + timedelta(days=3)).date()
        pv = preview_monthly_leave(self.db, self.res, d1, d2)
        self.assertFalse(pv["original_seat_available"])
        self.assertEqual(pv["conflict_order_no"], "RES-BLOCKER")
        self.assertEqual([s["id"] for s in pv["alternative_seats"]], [self.seat2.id])

        # 指定替代座位办理成功
        create_monthly_leave(self.db, self.res, d1, d2, self.admin, target_seat_id=self.seat2.id)
        self.assertEqual(self.res.seat_id, self.seat2.id)
        self.assertEqual(self.res.end_time, self.end + timedelta(days=2))

    def test_cancel_future_leave_restores_quota_and_end_time(self):
        d1 = (self.start + timedelta(days=3)).date()
        d2 = (self.start + timedelta(days=4)).date()
        res_data = create_monthly_leave(self.db, self.res, d1, d2, self.admin)
        leave_id = res_data["leave"]["id"]

        from app.models import ReservationLeave
        leave_obj = self.db.get(ReservationLeave, leave_id)
        out = cancel_or_resume_monthly_leave(self.db, leave_obj, self.admin)
        self.assertEqual(out["used_count"], 0)
        self.assertEqual(self.res.end_time, self.end)


if __name__ == "__main__":
    unittest.main()
