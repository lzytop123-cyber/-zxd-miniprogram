from contextlib import nullcontext
from datetime import datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import Mock, patch

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api.routes import admin, ble, payment
from app.models import AdminOperationLog, BillType, Reservation


class PaymentSafetyTests(IsolatedAsyncioTestCase):
    def setUp(self):
        self.db = Mock()
        self.order = SimpleNamespace(
            id=1, seat_id=2, status=0, pay_status=0, final_price=Decimal("10"),
            order_no="RES_TEST", pay_mchid=None, start_time=None, end_time=None,
        )

    async def test_payment_waits_for_seat_lock(self):
        with patch.object(payment, "RedisLock", return_value=nullcontext(SimpleNamespace(acquired=False))), \
             patch.object(payment, "seat_conflict_excluding", return_value=True):
            with self.assertRaises(HTTPException) as error:
                await payment.complete_reservation_wechat_payment(self.db, self.order, paid_fen=1000)
        self.assertEqual(error.exception.status_code, 503)
        self.assertEqual(self.order.status, 0)
        self.assertEqual(self.order.pay_status, 0)

    async def test_unconfirmed_refund_is_not_marked_refunded(self):
        with patch.object(payment, "RedisLock", return_value=nullcontext(SimpleNamespace(acquired=True))), \
             patch.object(payment, "seat_conflict_excluding", return_value=True), \
             patch.object(payment, "resolve_account_for_mchid"), \
             patch.object(payment.WechatPayService, "refund", return_value=False):
            with self.assertRaises(HTTPException) as error:
                await payment.complete_reservation_wechat_payment(self.db, self.order, paid_fen=1000)
        self.assertEqual(error.exception.status_code, 503)
        self.assertEqual(self.order.status, 3)
        self.assertNotEqual(self.order.pay_status, 2)

    async def test_cancelled_order_retries_refund_after_seat_conflict_clears(self):
        self.order.status = 3
        with patch.object(payment, "RedisLock", return_value=nullcontext(SimpleNamespace(acquired=True))), \
             patch.object(payment, "seat_conflict_excluding", return_value=False), \
             patch.object(payment, "resolve_account_for_mchid"), \
             patch.object(payment.WechatPayService, "refund", return_value=True):
            outcome = await payment.complete_reservation_wechat_payment(self.db, self.order, paid_fen=1000)
        self.assertEqual(outcome, "conflict")
        self.assertEqual(self.order.status, 3)
        self.assertEqual(self.order.pay_status, 2)
        self.assertIsNotNone(self.order.refunded_at)


class DoorScopeTests(TestCase):
    def test_store_admin_cannot_update_another_stores_lock(self):
        admin = SimpleNamespace(role="store", store_id=1)
        db = Mock()
        lock = ble.BleLock(id=9, store_id=2, lock_name="Original")
        db.get.return_value = lock
        with self.assertRaises(HTTPException) as error:
            ble.admin_update_lock(9, ble.BleLockUpdate(lock_name="Changed"), admin, db)
        self.assertEqual(error.exception.status_code, 403)
        self.assertEqual(lock.lock_name, "Original")


class AdminRefundListTests(TestCase):
    def test_refund_pending_filter_excludes_unpaid_and_other_stores(self):
        engine = create_engine("sqlite://")
        Reservation.__table__.create(engine)
        AdminOperationLog.__table__.create(engine)
        now = datetime.now()
        with Session(engine) as db:
            db.add_all([
                Reservation(
                    order_no=order_no, user_id=1, store_id=store_id, seat_id=1,
                    bill_type=BillType.hourly, start_time=now, end_time=now + timedelta(hours=1),
                    status=status, pay_status=0, paid_at=paid_at,
                )
                for order_no, store_id, status, paid_at in [
                    ("pending", 1, 3, now), ("unpaid", 1, 0, None), ("other", 2, 3, now),
                ]
            ])
            db.commit()
            with patch.object(admin, "_reservation_admin_item", side_effect=lambda db, row: {"order_no": row.order_no}):
                response = admin.admin_reservations(
                    page=1, page_size=20, refund_pending=True,
                    admin=SimpleNamespace(role="store", store_id=1), db=db,
                )
            self.assertEqual(response.data.total, 1)
            self.assertEqual(response.data.items, [{"order_no": "pending"}])
