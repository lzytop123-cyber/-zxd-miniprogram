"""Release regressions: real isolated database, no payment or door side effects."""
from contextlib import nullcontext
from datetime import date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api.routes import admin, admin_tools, payment, reservation
from app.db.session import Base
from app.models import AdminUser, BillType, Coupon, PayType, Reservation, Seat, Store, User, Zone
from app.schemas.reservation import ReservationCreateRequest, ReservationPayRequest
from app.services.booking import finalize_expired_reservation


class ReleaseTransactionTests(IsolatedAsyncioTestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.user = User(openid="release_test", nickname="Test", balance=Decimal("100"))
        self.store = Store(name="Release test", status=1)
        self.db.add_all([self.user, self.store])
        self.db.flush()
        zone = Zone(store_id=self.store.id, name="A")
        self.db.add(zone)
        self.db.flush()
        seats = [Seat(store_id=self.store.id, zone_id=zone.id, seat_code=str(i), status=1) for i in (1, 2)]
        self.db.add_all(seats)
        self.coupon = Coupon(user_id=self.user.id, discount_type="amount", discount_val=5,
                             min_amount=0, expire_date=date.today() + timedelta(days=7), status=0)
        self.db.add(self.coupon)
        self.db.flush()
        start = datetime.now() + timedelta(days=1)
        self.orders = [Reservation(order_no=f"RELEASE_{i}", user_id=self.user.id, store_id=self.store.id,
                                   seat_id=seat.id, bill_type=BillType.hourly, start_time=start,
                                   end_time=start + timedelta(hours=2), original_price=10, discount_price=5,
                                   final_price=5, coupon_id=self.coupon.id, status=0, pay_status=0)
                       for i, seat in enumerate(seats)]
        self.db.add_all(self.orders)
        self.db.commit()
        self.addCleanup(self.engine.dispose)
        self.addCleanup(self.db.close)
        for target in (reservation, payment):
            name = "_seat_lock" if target is reservation else "RedisLock"
            p = patch.object(target, name, side_effect=lambda *a, **kw: nullcontext(SimpleNamespace(acquired=True)))
            p.start()
            self.addCleanup(p.stop)
            p = patch.object(target, "finalize_reservation_after_pay", new_callable=AsyncMock)
            p.start()
            self.addCleanup(p.stop)

    async def pay(self, index=0, pay_type=PayType.balance, coupon_id=None):
        return await reservation.pay(ReservationPayRequest(order_no=self.orders[index].order_no,
                                      pay_type=pay_type, coupon_id=coupon_id), self.user, self.db)

    async def test_balance_payment_uses_persisted_coupon_when_client_omits_id(self):
        await self.pay()
        self.db.refresh(self.coupon)
        self.assertEqual(self.coupon.status, 1)
        self.assertEqual(self.user.balance, Decimal("95"))

    async def test_precreated_discount_order_cannot_reuse_consumed_coupon(self):
        await self.pay(coupon_id=self.coupon.id)
        with self.assertRaises(HTTPException) as error:
            await self.pay(index=1)
        self.assertEqual(error.exception.status_code, 409)
        self.db.rollback()
        self.assertEqual(self.db.get(User, self.user.id).balance, Decimal("95"))
        self.assertEqual(self.db.get(Reservation, self.orders[1].id).pay_status, 0)

    async def test_payment_rejects_coupon_different_from_order(self):
        with self.assertRaises(HTTPException) as error:
            await self.pay(coupon_id=self.coupon.id + 100)
        self.assertEqual(error.exception.status_code, 400)
        self.assertEqual(self.user.balance, Decimal("100"))

    async def test_wechat_prepay_reserves_coupon_for_exact_order(self):
        params = dict(timeStamp="1", nonceStr="test", package="prepay_id=test", paySign="test")
        with patch.object(reservation, "resolve_pay_account", return_value=SimpleNamespace(mchid="TEST")), \
             patch.object(reservation.WechatPayService, "create_jsapi_order", return_value=params):
            await self.pay(pay_type=PayType.wechat)
            self.db.refresh(self.coupon)
            self.assertEqual(self.coupon.status, 2)
            self.assertEqual(self.coupon.reserved_order_no, self.orders[0].order_no)
            with self.assertRaises(HTTPException) as error:
                await self.pay(index=1, pay_type=PayType.wechat)
            self.assertEqual(error.exception.status_code, 409)

    async def test_unpaid_prepay_cancellation_releases_only_its_own_coupon(self):
        params = dict(timeStamp="1", nonceStr="test", package="prepay_id=test", paySign="test")
        with patch.object(reservation, "resolve_pay_account", return_value=SimpleNamespace(mchid="TEST")), \
             patch.object(reservation.WechatPayService, "create_jsapi_order", return_value=params):
            await self.pay(pay_type=PayType.wechat)
        reservation.cancel(self.orders[1].id, self.user, self.db)
        self.db.refresh(self.coupon)
        self.assertEqual(self.coupon.status, 2)
        reservation.cancel(self.orders[0].id, self.user, self.db)
        self.db.refresh(self.coupon)
        self.assertEqual(self.coupon.status, 0)

    async def test_late_callback_after_cancellation_does_not_consume_another_orders_coupon(self):
        reservation.cancel(self.orders[0].id, self.user, self.db)
        await self.pay(index=1)
        with patch.object(payment, "resolve_account_for_mchid"), \
             patch.object(payment.WechatPayService, "refund", return_value=True):
            outcome = await payment.complete_reservation_wechat_payment(self.db, self.orders[0], paid_fen=500)
        self.db.refresh(self.coupon)
        self.assertEqual(outcome, "conflict")
        self.assertEqual(self.coupon.status, 1)
        self.assertEqual(self.coupon.reserved_order_no, self.orders[1].order_no)

    async def test_callback_refunds_order_when_coupon_was_already_used_elsewhere(self):
        await self.pay()
        with patch.object(payment, "resolve_account_for_mchid"), \
             patch.object(payment.WechatPayService, "refund", return_value=True):
            outcome = await payment.complete_reservation_wechat_payment(self.db, self.orders[1], paid_fen=500)
        self.assertEqual(outcome, "conflict")
        self.assertEqual((self.orders[1].status, self.orders[1].pay_status), (3, 2))
        self.assertEqual(self.coupon.status, 1)

    async def test_payment_method_cannot_switch_after_wechat_prepay(self):
        self.orders[0].pay_type, self.orders[0].pay_mchid = PayType.wechat, "TEST"
        self.db.commit()
        with self.assertRaises(HTTPException) as error:
            await self.pay()
        self.assertEqual(error.exception.status_code, 409)

    async def test_stale_create_cannot_reprice_order_after_prepay_started(self):
        order = self.orders[0]
        order.coupon_id = None
        order.original_price, order.discount_price, order.final_price = 10, 0, 10
        self.db.commit()
        self.assertIsNone(order.pay_mchid)
        order_id, start, end, seat = order.id, order.start_time, order.end_time, self.db.get(Seat, order.seat_id)
        with Session(self.engine) as other:
            current = other.get(Reservation, order_id)
            current.pay_type, current.pay_mchid = PayType.wechat, "TEST"
            other.commit()
        body = ReservationCreateRequest(store_id=self.store.id, seat_id=seat.id, start_time=start, end_time=end)
        with patch.object(reservation, "_prepare_booking", return_value=(start, end, Decimal("2"), seat, Decimal("20"))):
            with self.assertRaises(HTTPException) as error:
                reservation.create(body, self.user, self.db)
        self.assertEqual(error.exception.status_code, 409)
        self.db.rollback()
        self.assertEqual(self.db.get(Reservation, order_id).final_price, Decimal("10"))

    async def test_booking_end_before_payment_timeout_releases_reserved_coupon(self):
        params = dict(timeStamp="1", nonceStr="test", package="prepay_id=test", paySign="test")
        with patch.object(reservation, "resolve_pay_account", return_value=SimpleNamespace(mchid="TEST")), \
             patch.object(reservation.WechatPayService, "create_jsapi_order", return_value=params):
            await self.pay(pay_type=PayType.wechat)
        finalize_expired_reservation(self.db, self.orders[0], self.orders[0].end_time + timedelta(seconds=1))
        self.db.commit()
        self.db.refresh(self.coupon)
        self.assertEqual(self.coupon.status, 0)

    async def test_callback_uses_order_coupon_without_attach(self):
        outcome = await payment.complete_reservation_wechat_payment(self.db, self.orders[0], paid_fen=500)
        self.assertEqual(outcome, "paid")
        self.db.refresh(self.coupon)
        self.assertEqual(self.coupon.status, 1)

    async def test_failed_user_refund_stays_pending_and_retry_uses_same_identity(self):
        order = self.orders[0]
        order.pay_type, order.pay_status = PayType.wechat, 1
        self.db.commit()
        with patch.object(reservation.WechatPayService, "refund", side_effect=[False, True]) as refund:
            with self.assertRaises(HTTPException) as error:
                reservation.cancel(order.id, self.user, self.db)
            self.assertEqual(error.exception.status_code, 503)
            self.db.refresh(order)
            self.assertEqual((order.status, order.pay_status, order.refunded_at), (3, 1, None))
            reservation.cancel(order.id, self.user, self.db)
            self.assertEqual(order.pay_status, 2)
            self.assertIsNotNone(order.refunded_at)
            ids = [call.kwargs["confirmed_refund_no"] for call in refund.call_args_list]
            self.assertEqual(ids, [f"RF_CANCEL_{order.order_no}"] * 2)

    async def test_failed_admin_refund_is_not_completed(self):
        order = self.orders[0]
        order.pay_type, order.pay_status = PayType.wechat, 1
        self.db.commit()
        actor = SimpleNamespace(role="hq", store_id=None)
        with patch.object(reservation.WechatPayService, "refund", return_value=False):
            with self.assertRaises(HTTPException) as error:
                admin.admin_cancel_reservation(order.id, actor, self.db)
        self.assertEqual(error.exception.status_code, 503)
        self.assertEqual((order.status, order.pay_status), (3, 1))

    async def test_pending_wechat_refund_cannot_be_manually_marked_complete(self):
        order = self.orders[0]
        order.status, order.pay_type, order.pay_status = 3, PayType.wechat, 1
        actor = AdminUser(username="release_admin", password_hash="unused", role="hq")
        self.db.add(actor)
        self.db.commit()
        with self.assertRaises(HTTPException) as error:
            admin_tools.mark_reservation_refund(order.id, admin_tools.RefundMarkRequest(remark="manual"), actor, self.db)
        self.assertEqual(error.exception.status_code, 409)
        self.assertEqual(order.pay_status, 1)

    async def test_unpaid_other_order_cancellation_does_not_restore_used_coupon(self):
        await self.pay(coupon_id=self.coupon.id)
        reservation.cancel(self.orders[1].id, self.user, self.db)
        self.db.refresh(self.coupon)
        self.assertEqual(self.coupon.status, 1)

    async def test_confirmed_balance_cancellation_returns_coupon_once(self):
        await self.pay(coupon_id=self.coupon.id)
        reservation.cancel(self.orders[0].id, self.user, self.db)
        self.db.refresh(self.coupon)
        self.assertEqual(self.coupon.status, 0)
        self.assertEqual(self.user.balance, Decimal("100"))
        reservation.cancel(self.orders[0].id, self.user, self.db)
        self.assertEqual(self.user.balance, Decimal("100"))


if __name__ == "__main__":
    import unittest
    unittest.main()
