"""收款管理契约测试：临时数据库，不访问实际账单或支付服务。"""
import os
os.environ["DATABASE_URL"] = "sqlite://"

import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Barrier
from unittest.mock import patch
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_current_admin
from app.db.session import Base, get_db
from app.models import AdminUser, BillType, CardPurchaseOrder, PayType, PricingRule, RechargeOrder, Reservation, User


class ReceiptsTests(unittest.TestCase):
    def setUp(self):
        from app.api.routes import admin_receipts
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.admin = AdminUser(username="test", password_hash="unused")
        self.db.add_all([self.admin, User(id=1, openid="test")])
        self.db.commit()
        self.app = FastAPI()
        self.app.include_router(admin_receipts.router)
        self.app.dependency_overrides[get_db] = lambda: self.db
        self.app.dependency_overrides[get_current_admin] = lambda: self.admin
        self.client = TestClient(self.app)

    def tearDown(self):
        if hasattr(self, "db"):
            self.client.close()
            self.db.close()
            self.engine.dispose()

    def receipt(self, **changes):
        body = dict(channel="wechat_transfer", amount="100.00", received_on="2025-08-31", customer="小王", request_id=str(uuid4()))
        body.update(changes)
        res = self.client.post("/admin/receipts", json=body)
        self.assertEqual(res.status_code, 200, res.text)
        return res.json()["data"]

    def refund(self, receipt_id, **changes):
        body = dict(amount="30.00", refunded_on="2025-09-01", reason="退还余款", completed=True, request_id=str(uuid4()))
        body.update(changes)
        return self.client.post(f"/admin/receipts/{receipt_id}/refunds", json=body)

    def summary(self, month):
        return self.client.get("/admin/receipts/summary", params={"year": 2025, "month": month}).json()["data"]

    def test_cross_month_refund_uses_refund_date(self):
        row = self.receipt()
        self.assertEqual(self.refund(row["id"]).status_code, 200)
        aug, sep = self.summary(8), self.summary(9)
        self.assertEqual(Decimal(aug["month"]["net"]), Decimal("100"))
        self.assertEqual(Decimal(sep["month"]["net"]), Decimal("-30"))
        self.assertEqual(Decimal(sep["year"]["net"]), Decimal("70"))
        data = self.client.get("/admin/receipts/refunds", params={"year": 2025, "month": 9}).json()["data"]
        self.assertEqual(data["total"], 1)

    def test_refund_cap_and_retries(self):
        key = str(uuid4())
        row = self.receipt(request_id=key)
        self.assertEqual(self.receipt(request_id=key)["id"], row["id"])
        refund_key = str(uuid4())
        first = self.refund(row["id"], request_id=refund_key)
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(self.refund(row["id"], request_id=refund_key).json(), first.json())
        self.assertEqual(self.refund(row["id"], amount="70.01").status_code, 400)
        self.assertEqual(self.refund(row["id"], amount="70").status_code, 200)
        self.assertEqual(self.refund(row["id"], amount="0.01").status_code, 400)
        self.assertEqual(Decimal(self.summary(9)["year"]["net"]), Decimal("0"))

    def test_validation_and_auth(self):
        for amount in ["0", "-1", "0.001", "NaN", "100000000"]:
            result = self.client.post("/admin/receipts", json=dict(channel="meituan", amount=amount, received_on="2025-01-01", request_id=str(uuid4())))
            self.assertEqual(result.status_code, 422, result.text)
        row = self.receipt()
        self.assertEqual(self.refund(row["id"], completed=False).status_code, 422)
        self.assertEqual(self.refund(row["id"], refunded_on="2025-08-30").status_code, 400)
        self.assertEqual(self.refund(999).status_code, 404)
        self.app.dependency_overrides.pop(get_current_admin)
        self.assertEqual(self.client.get("/admin/receipts").status_code, 401)

    def test_request_key_cannot_silently_accept_different_amount(self):
        key = str(uuid4())
        row = self.receipt(request_id=key)
        result = self.client.post("/admin/receipts", json=dict(channel="wechat_transfer", amount="200", received_on="2025-08-31", customer="小王", request_id=key))
        self.assertEqual(result.status_code, 409)
        refund_key = str(uuid4())
        self.assertEqual(self.refund(row["id"], request_id=refund_key).status_code, 200)
        self.assertEqual(self.refund(row["id"], request_id=refund_key, amount="40").status_code, 409)

    def test_channel_reference_uniqueness_and_annual_filter(self):
        self.receipt(channel="meituan", amount="12.30", reference="MT1")
        result = self.client.post("/admin/receipts", json=dict(channel="meituan", amount="12.30", received_on="2025-08-31", reference="MT1", request_id=str(uuid4())))
        self.assertEqual(result.status_code, 409)
        self.receipt(channel="douyin", amount="0.10", received_on="2025-01-01")
        self.receipt(channel="douyin", amount="0.20", received_on="2025-12-31")
        self.receipt(channel="douyin", amount="900", received_on="2024-12-31")
        summary = self.client.get("/admin/receipts/summary", params={"year": 2025, "channel": "douyin"}).json()["data"]
        self.assertEqual(summary["year"]["received"], "0.30")
        rows = self.client.get("/admin/receipts", params={"year": 2025, "channel": "douyin", "page_size": 1, "page": 2}).json()["data"]
        self.assertEqual(rows["total"], 2)
        self.assertEqual(rows["items"][0]["received_on"], "2025-01-01")

    def test_paid_reservation_remains_visible_after_refund(self):
        order = Reservation(order_no="RES1", user_id=1, store_id=1, seat_id=1, bill_type=BillType.hourly, start_time=datetime(2025, 8, 31, 10), end_time=datetime(2025, 8, 31, 11), final_price=Decimal("18"), pay_type=PayType.wechat, pay_status=1, paid_at=datetime(2025, 8, 31, 23, 59))
        self.db.add(order)
        self.db.commit()
        self.assertEqual(self.client.post("/admin/receipts/sync-wechat").status_code, 200)
        order.pay_status = 2
        self.db.commit()
        self.assertEqual(self.client.post("/admin/receipts/sync-wechat").status_code, 200)
        summary = self.summary(8)
        self.assertEqual(summary["refunds_to_review"], 1)
        self.assertEqual(summary["month"]["received"], "18.00")
        rows = self.client.get("/admin/receipts", params={"needs_refund": True}).json()["data"]
        self.assertEqual(rows["total"], 1)
        result = self.refund(rows["items"][0]["id"], amount="18")
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(self.summary(9)["refunds_to_review"], 0)
        self.assertEqual(self.summary(9)["month"]["net"], "-18.00")

    def test_platform_payment_time_uses_beijing_date(self):
        from app.services.receipts import payment_time
        self.assertEqual(payment_time("2025-08-31T16:01:00Z"), datetime(2025, 9, 1, 0, 1))
        self.assertEqual(payment_time("2025-12-31T23:59:59+08:00"), datetime(2025, 12, 31, 23, 59, 59))

    def test_fulfillment_preserves_original_payment_time_on_retry(self):
        from app.services.booking import fulfill_recharge_order
        from app.services.card_service import fulfill_card_purchase
        recharge = RechargeOrder(order_no="RCH-NEW", user_id=1, amount=Decimal("50"), pay_status=0)
        rule = PricingRule(store_id=1, bill_type=BillType.daily, price=Decimal("20"), valid_days=1)
        self.db.add_all([recharge, rule])
        self.db.flush()
        purchase = CardPurchaseOrder(order_no="CRD-NEW", user_id=1, store_id=1, pricing_rule_id=rule.id, bill_type=BillType.daily, amount=Decimal("20"), pay_type=PayType.wechat)
        self.db.add(purchase)
        self.db.flush()
        fulfill_recharge_order(self.db, recharge, success_time="2025-08-31T16:01:00Z")
        fulfill_card_purchase(self.db, purchase, success_time="2025-08-31T16:02:00Z")
        self.db.commit()
        fulfill_recharge_order(self.db, recharge, success_time="2025-10-01T01:00:00Z")
        fulfill_card_purchase(self.db, purchase, success_time="2025-10-01T01:00:00Z")
        self.db.commit()
        self.assertEqual(recharge.paid_at, datetime(2025, 9, 1, 0, 1))
        self.assertEqual(purchase.paid_at, datetime(2025, 9, 1, 0, 2))
        self.assertEqual(self.db.get(User, 1).balance, Decimal("50"))

    def test_reservation_payment_date_and_refunded_callback_retry(self):
        import asyncio
        from unittest.mock import AsyncMock
        from app.api.routes import payment
        order = Reservation(order_no="RES-TIME", user_id=1, store_id=1, seat_id=1, bill_type=BillType.hourly, start_time=datetime(2025, 9, 1, 10), end_time=datetime(2025, 9, 1, 11), final_price=Decimal("18"), pay_status=0)
        self.db.add(order)
        self.db.commit()
        # Isolate Redis/door notification side effects; real payment state changes stay under test.
        with patch.object(payment, "RedisLock", return_value=nullcontext()), patch.object(payment, "finalize_reservation_after_pay", new_callable=AsyncMock):
            result = asyncio.run(payment.complete_reservation_wechat_payment(self.db, order, paid_fen=1800, success_time="2025-08-31T16:01:00Z"))
            self.assertEqual(result, "paid")
            self.assertEqual(order.paid_at, datetime(2025, 9, 1, 0, 1))
            order.pay_status = 2
            self.db.commit()
            asyncio.run(payment.complete_reservation_wechat_payment(self.db, order, paid_fen=1800, success_time="2025-09-02T16:01:00Z"))
            self.assertEqual(order.pay_status, 2)
            self.assertEqual(order.paid_at, datetime(2025, 9, 1, 0, 1))

    def test_migration_creates_tables_and_nullable_dates_idempotently(self):
        from app.models.receipts import Receipt, ReceiptRefund
        from app.services import schema_migrate
        self.db.commit()
        ReceiptRefund.__table__.drop(self.engine)
        Receipt.__table__.drop(self.engine)
        with self.engine.begin() as conn:
            conn.execute(text("ALTER TABLE reservations DROP COLUMN paid_at"))
            conn.execute(text("ALTER TABLE card_purchase_orders DROP COLUMN paid_at"))
        with patch.object(schema_migrate, "engine", self.engine):
            for _ in range(2):
                result = schema_migrate.run_schema_migrations(self.db)
                self.assertFalse(result["errors"], result["errors"])
        inspector = inspect(self.engine)
        self.assertTrue(inspector.has_table("receipts"))
        self.assertTrue(inspector.has_table("receipt_refunds"))
        for table in ("reservations", "card_purchase_orders"):
            self.assertTrue(next(c for c in inspector.get_columns(table) if c["name"] == "paid_at")["nullable"])

    def test_concurrent_refunds_do_not_exceed_receipt(self):
        from app.api.routes import admin_receipts
        from app.models.receipts import ReceiptRefund
        with TemporaryDirectory(prefix="receipt-test-") as directory:
            engine = create_engine(f"sqlite:///{Path(directory) / 'test.db'}", connect_args={"check_same_thread": False})
            try:
                Base.metadata.create_all(engine)
                factory = sessionmaker(bind=engine)
                with factory() as db:
                    db.add(AdminUser(id=1, username="test", password_hash="unused"))
                    db.commit()
                app = FastAPI()
                app.include_router(admin_receipts.router)
                def session():
                    with factory() as db:
                        yield db
                app.dependency_overrides[get_db] = session
                app.dependency_overrides[get_current_admin] = lambda: AdminUser(id=1, username="test")
                with TestClient(app) as client:
                    for same_key in (False, True):
                        created = client.post("/admin/receipts", json=dict(channel="douyin", amount="100", received_on="2025-01-01", request_id=str(uuid4())))
                        self.assertEqual(created.status_code, 200, created.text)
                        receipt_id = created.json()["data"]["id"]
                        barrier = Barrier(2)
                        request_key = str(uuid4())
                        def submit(_):
                            barrier.wait(timeout=5)
                            return client.post(f"/admin/receipts/{receipt_id}/refunds", json=dict(amount="60", refunded_on="2025-02-01", reason="partial", completed=True, request_id=request_key if same_key else str(uuid4()))).status_code
                        with ThreadPoolExecutor(max_workers=2) as executor:
                            statuses = sorted(executor.map(submit, range(2)))
                        self.assertEqual(statuses, [200, 200] if same_key else [200, 400])
                        with factory() as db:
                            rows = db.scalars(select(ReceiptRefund).where(ReceiptRefund.receipt_id == receipt_id)).all()
                            self.assertEqual(len(rows), 1)
                            self.assertEqual(rows[0].amount, Decimal("60"))
            finally:
                engine.dispose()

    def test_sync_excludes_balance_and_missing_dates_and_is_idempotent(self):
        self.db.add_all([
            RechargeOrder(order_no="RCH1", user_id=1, amount=Decimal("50"), pay_status=1, pay_type=PayType.wechat, paid_at=datetime(2025, 9, 2)),
            RechargeOrder(order_no="RCH2", user_id=1, amount=Decimal("80"), pay_status=0),
            CardPurchaseOrder(order_no="CRD1", user_id=1, store_id=1, bill_type=BillType.daily, amount=Decimal("20"), pay_status=1, pay_type=PayType.balance),
            CardPurchaseOrder(order_no="CRD2", user_id=1, store_id=1, bill_type=BillType.daily, amount=Decimal("30"), pay_status=1, pay_type=PayType.wechat),
        ])
        self.db.commit()
        for _ in range(2):
            result = self.client.post("/admin/receipts/sync-wechat")
            self.assertEqual(result.status_code, 200, result.text)
        summary = self.summary(9)
        self.assertEqual(Decimal(summary["month"]["received"]), Decimal("50"))
        self.assertEqual(summary["missing_dates"], 1)
        rows = self.client.get("/admin/receipts", params={"needs_date": True}).json()["data"]
        self.assertEqual(rows["total"], 1)
        row = rows["items"][0]
        self.assertEqual(self.refund(row["id"]).status_code, 400)
        result = self.client.patch(f'/admin/receipts/{row["id"]}/date', json={"received_on": "2025-09-03"})
        self.assertEqual(result.status_code, 200, result.text)
        self.client.post("/admin/receipts/sync-wechat")
        self.assertEqual(Decimal(self.summary(9)["month"]["received"]), Decimal("80"))


if __name__ == "__main__":
    unittest.main()
