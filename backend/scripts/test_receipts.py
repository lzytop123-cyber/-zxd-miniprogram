"""收款管理契约测试：临时数据库，不访问实际账单或支付服务。"""
import os
os.environ["DATABASE_URL"] = "sqlite://"

import unittest
from concurrent.futures import ThreadPoolExecutor
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
from app.models import AdminUser, BillType, CardPurchaseOrder, PayType, PricingRule, RechargeOrder, Reservation, Store, User


class ReceiptsTests(unittest.TestCase):
    def setUp(self):
        from app.api.routes import admin_receipts
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.admin = AdminUser(username="test", password_hash="unused")
        self.db.add_all([
            self.admin,
            User(id=1, openid="test"),
            Store(id=1, name="知行岛自习室(千峰南路店)"),
        ])
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
        body = dict(channel="wechat_transfer", amount="100.00", received_on="2025-08-31", customer="小王", store_id=1, request_id=str(uuid4()))
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

    def test_cross_month_refund_stays_on_receipt_month(self):
        row = self.receipt()
        self.assertEqual(self.refund(row["id"]).status_code, 200)
        aug, sep = self.summary(8), self.summary(9)
        self.assertEqual(Decimal(aug["month"]["received"]), Decimal("100"))
        self.assertEqual(Decimal(aug["month"]["refunded"]), Decimal("30"))
        self.assertEqual(Decimal(aug["month"]["net"]), Decimal("70"))
        self.assertEqual(Decimal(sep["month"]["net"]), Decimal("0"))
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
            result = self.client.post("/admin/receipts", json=dict(channel="meituan", amount=amount, received_on="2025-01-01", store_id=1, request_id=str(uuid4())))
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
        result = self.client.post("/admin/receipts", json=dict(channel="wechat_transfer", amount="200", received_on="2025-08-31", customer="小王", store_id=1, request_id=key))
        self.assertEqual(result.status_code, 409)
        refund_key = str(uuid4())
        self.assertEqual(self.refund(row["id"], request_id=refund_key).status_code, 200)
        self.assertEqual(self.refund(row["id"], request_id=refund_key, amount="40").status_code, 409)

    def test_channel_reference_uniqueness_and_annual_filter(self):
        self.receipt(channel="meituan", amount="12.30", reference="MT1")
        result = self.client.post("/admin/receipts", json=dict(channel="meituan", amount="12.30", received_on="2025-08-31", reference="MT1", store_id=1, request_id=str(uuid4())))
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
        self.assertEqual(self.summary(8)["month"]["net"], "0.00")
        self.assertEqual(self.summary(9)["month"]["net"], "0.00")

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
        class _HeldLock:
            acquired = True

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        with patch.object(payment, "RedisLock", return_value=_HeldLock()), patch.object(payment, "finalize_reservation_after_pay", new_callable=AsyncMock):
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
        store_col = next(c for c in inspector.get_columns("receipts") if c["name"] == "store_id")
        self.assertTrue(store_col["nullable"])

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
                    db.add(Store(id=1, name="知行岛自习室(千峰南路店)"))
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
                        created = client.post("/admin/receipts", json=dict(channel="douyin", amount="100", received_on="2025-01-01", store_id=1, request_id=str(uuid4())))
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

    def test_hq_store_id_filters_associated_receipts(self):
        from datetime import date
        from app.models.receipts import Receipt

        self.db.add_all([
            CardPurchaseOrder(
                order_no="CA", user_id=1, store_id=1, bill_type=BillType.daily,
                amount=Decimal("40"), pay_status=1, pay_type=PayType.wechat,
            ),
            CardPurchaseOrder(
                order_no="CB", user_id=1, store_id=2, bill_type=BillType.daily,
                amount=Decimal("60"), pay_status=1, pay_type=PayType.wechat,
            ),
            Receipt(
                source_key="card:CA", channel="wechat_pay", amount=Decimal("40"),
                received_on=date(2025, 8, 1), reference="CA",
            ),
            Receipt(
                source_key="card:CB", channel="wechat_pay", amount=Decimal("60"),
                received_on=date(2025, 8, 1), reference="CB",
            ),
            Receipt(
                source_key="manual:hq-only", channel="wechat_transfer", amount=Decimal("10"),
                received_on=date(2025, 8, 1), reference="manual-hq",
            ),
        ])
        self.db.commit()
        all_rows = self.client.get("/admin/receipts", params={"year": 2025, "month": 8}).json()["data"]
        self.assertEqual(all_rows["total"], 3)
        store1 = self.client.get(
            "/admin/receipts", params={"year": 2025, "month": 8, "store_id": 1}
        ).json()["data"]
        self.assertEqual(store1["total"], 1)
        self.assertEqual(store1["items"][0]["reference"], "CA")
        sum1 = self.client.get(
            "/admin/receipts/summary", params={"year": 2025, "month": 8, "store_id": 1}
        ).json()["data"]
        self.assertEqual(Decimal(sum1["month"]["received"]), Decimal("40"))
        mgr = AdminUser(username="mgr", password_hash="x", role="store", store_id=1)
        self.app.dependency_overrides[get_current_admin] = lambda: mgr
        forbidden = self.client.get("/admin/receipts", params={"year": 2025, "month": 8, "store_id": 2})
        self.assertEqual(forbidden.status_code, 403)
        forced = self.client.get("/admin/receipts", params={"year": 2025, "month": 8}).json()["data"]
        self.assertEqual(forced["total"], 1)

    def test_sync_excludes_balance_falls_back_to_created_at_and_is_idempotent(self):
        from app.models.receipts import Receipt
        self.db.add_all([
            RechargeOrder(order_no="RCH1", user_id=1, amount=Decimal("50"), pay_status=1, pay_type=PayType.wechat, paid_at=datetime(2025, 9, 2)),
            RechargeOrder(order_no="RCH2", user_id=1, amount=Decimal("80"), pay_status=0),
            CardPurchaseOrder(order_no="CRD1", user_id=1, store_id=1, bill_type=BillType.daily, amount=Decimal("20"), pay_status=1, pay_type=PayType.balance),
            CardPurchaseOrder(order_no="CRD2", user_id=1, store_id=1, bill_type=BillType.daily, amount=Decimal("30"), pay_status=1, pay_type=PayType.wechat, created_at=datetime(2025, 9, 3, 10)),
        ])
        self.db.commit()
        # Pre-seed a stale Receipt with no date to prove the sync also backfills existing rows.
        self.db.add(Receipt(source_key="card:CRD2", channel="wechat_pay", amount=Decimal("30"), reference="CRD2", customer="老王", remark="套餐购买"))
        self.db.commit()
        for _ in range(2):
            result = self.client.post("/admin/receipts/sync-wechat")
            self.assertEqual(result.status_code, 200, result.text)
        summary = self.summary(9)
        self.assertEqual(Decimal(summary["month"]["received"]), Decimal("80"))
        self.assertEqual(summary["missing_dates"], 0)
        # 补日期 endpoint still works when both paid_at and created_at are missing.
        self.db.add(Receipt(source_key="manual-orphan", channel="wechat_transfer", amount=Decimal("5"), reference="orphan", customer="孤儿"))
        self.db.commit()
        orphan = self.db.scalar(select(Receipt).where(Receipt.source_key == "manual-orphan"))
        result = self.client.patch(f"/admin/receipts/{orphan.id}/date", json={"received_on": "2025-09-05"})
        self.assertEqual(result.status_code, 200, result.text)

    def test_migration_adds_store_id_on_existing_receipts_table(self):
        from app.models.receipts import Receipt, ReceiptRefund
        from app.services import schema_migrate
        self.db.commit()
        ReceiptRefund.__table__.drop(self.engine)
        Receipt.__table__.drop(self.engine)
        with self.engine.begin() as conn:
            conn.execute(text(
                "CREATE TABLE receipts ("
                "id INTEGER PRIMARY KEY, "
                "source_key VARCHAR(100) NOT NULL UNIQUE, "
                "channel VARCHAR(30) NOT NULL, "
                "amount NUMERIC(10, 2) NOT NULL, "
                "refunded_amount NUMERIC(10, 2) NOT NULL DEFAULT 0, "
                "received_on DATE, customer VARCHAR(100), reference VARCHAR(100), "
                "remark VARCHAR(500), source_refunded BOOLEAN NOT NULL DEFAULT 0, "
                "created_at DATETIME)"
            ))
        with patch.object(schema_migrate, "engine", self.engine):
            first = schema_migrate.run_schema_migrations(self.db)
            second = schema_migrate.run_schema_migrations(self.db)
        self.assertFalse(first["errors"], first["errors"])
        self.assertFalse(second["errors"], second["errors"])
        columns = {c["name"]: c for c in inspect(self.engine).get_columns("receipts")}
        self.assertIn("store_id", columns)
        self.assertTrue(columns["store_id"]["nullable"])

    def test_manual_receipt_requires_store(self):
        missing = self.client.post("/admin/receipts", json=dict(
            channel="wechat_transfer", amount="10.00", received_on="2026-01-02", request_id=str(uuid4()),
        ))
        self.assertEqual(missing.status_code, 422, missing.text)
        unknown = self.client.post("/admin/receipts", json=dict(
            channel="wechat_transfer", amount="10.00", received_on="2026-01-02", store_id=999, request_id=str(uuid4()),
        ))
        self.assertEqual(unknown.status_code, 400, unknown.text)
        self.db.add(Store(id=2, name="理工大店"))
        mgr = AdminUser(username="mgr-store", password_hash="x", role="store", store_id=1)
        self.db.add(mgr)
        self.db.commit()
        self.app.dependency_overrides[get_current_admin] = lambda: mgr
        other = self.client.post("/admin/receipts", json=dict(
            channel="wechat_transfer", amount="10.00", received_on="2026-01-02", store_id=2, request_id=str(uuid4()),
        ))
        self.assertEqual(other.status_code, 403, other.text)
        own = self.receipt(amount="10.00", received_on="2026-01-02")
        self.assertEqual(own["store_id"], 1)

    def test_new_receipts_inherit_order_store(self):
        from app.models import MeituanOrder, MeituanOrderStatus
        from app.models.receipts import Receipt
        self.db.add(Store(id=2, name="理工大店"))
        self.db.add_all([
            Reservation(
                order_no="RES-S1", user_id=1, store_id=1, seat_id=1, bill_type=BillType.hourly,
                start_time=datetime(2026, 11, 5, 10), end_time=datetime(2026, 11, 5, 11),
                final_price=Decimal("62.70"), pay_type=PayType.wechat, pay_status=1,
                paid_at=datetime(2026, 11, 5, 9),
            ),
            Reservation(
                order_no="RES-S2", user_id=1, store_id=2, seat_id=2, bill_type=BillType.hourly,
                start_time=datetime(2026, 11, 13, 15), end_time=datetime(2026, 11, 13, 16),
                final_price=Decimal("17.00"), pay_type=PayType.wechat, pay_status=1,
                paid_at=datetime(2026, 11, 13, 15),
            ),
            MeituanOrder(
                coupon_code="MT-S2", user_id=1, store_id=2, status=MeituanOrderStatus.verified,
                verified_at=datetime(2026, 11, 13, 16), deal_name="体验",
                meituan_raw={"payAmount": 800, "receipt_channel": "douyin"},
            ),
            MeituanOrder(
                coupon_code="MT-REVIEW", user_id=1, store_id=1, status=MeituanOrderStatus.verified,
                verified_at=datetime(2026, 11, 2, 12), deal_name="待核", deal_price=Decimal("12"),
                meituan_raw={"ticketData": {"dealPrice": 12}},
            ),
            RechargeOrder(
                order_no="RCH-NOS", user_id=1, amount=Decimal("15.00"), pay_status=1,
                pay_type=PayType.wechat, paid_at=datetime(2026, 11, 1, 12),
            ),
        ])
        self.db.commit()
        synced = self.client.post("/admin/receipts/sync")
        self.assertEqual(synced.status_code, 200, synced.text)
        rows = {row.reference: row for row in self.db.scalars(select(Receipt)).all()}
        self.assertEqual(rows["RES-S1"].store_id, 1)
        self.assertEqual(rows["RES-S2"].store_id, 2)
        self.assertEqual(rows["MT-S2"].store_id, 2)
        self.assertIsNone(rows["RCH-NOS"].store_id)
        review = self.db.scalar(select(MeituanOrder).where(MeituanOrder.coupon_code == "MT-REVIEW"))
        confirmed = self.client.post(
            f"/admin/receipts/platform-review/{review.id}/confirm",
            json={"channel": "meituan", "amount": "12.00", "received_on": "2026-11-02", "confirmed": True},
        )
        self.assertEqual(confirmed.status_code, 200, confirmed.text)
        self.assertEqual(confirmed.json()["data"]["store_id"], 1)

    def test_backfill_attributes_unscoped_history_without_double_count(self):
        from datetime import date
        from app.models import MeituanOrder, MeituanOrderStatus
        from app.models.receipts import Receipt
        from app.services.receipt_store_backfill import backfill_receipt_stores

        self.db.add(Store(id=2, name="理工大店"))
        self.db.add_all([
            Reservation(
                order_no="S1", user_id=1, store_id=1, seat_id=1, bill_type=BillType.hourly,
                start_time=datetime(2026, 11, 5, 10), end_time=datetime(2026, 11, 5, 11),
                final_price=Decimal("62.70"), pay_type=PayType.wechat, pay_status=1,
            ),
            Reservation(
                order_no="S2", user_id=1, store_id=2, seat_id=2, bill_type=BillType.hourly,
                start_time=datetime(2026, 11, 13, 15), end_time=datetime(2026, 11, 13, 16),
                final_price=Decimal("17.00"), pay_type=PayType.wechat, pay_status=1,
            ),
        ])
        self.db.flush()
        unscoped = MeituanOrder(
            coupon_code="MONTH", user_id=1, store_id=None, status=MeituanOrderStatus.verified,
            verified_at=datetime(2026, 11, 8, 12), deal_name="月卡",
        )
        kept = MeituanOrder(
            coupon_code="LGD", user_id=1, store_id=2, status=MeituanOrderStatus.verified,
            verified_at=datetime(2026, 11, 13, 16), deal_name="理工大",
        )
        pending = MeituanOrder(
            coupon_code="PEND", user_id=1, store_id=None, status=MeituanOrderStatus.pending,
            deal_name="未核销",
        )
        self.db.add_all([unscoped, kept, pending])
        self.db.flush()
        self.db.add_all([
            Receipt(source_key="reservation:S1", channel="wechat_pay", amount=Decimal("62.70"), received_on=date(2026, 11, 5), reference="S1"),
            Receipt(source_key=f"platform:{unscoped.id}", channel="meituan", amount=Decimal("50.00"), received_on=date(2026, 11, 8), reference="MONTH"),
            Receipt(source_key="manual:old", channel="wechat_transfer", amount=Decimal("30.00"), refunded_amount=Decimal("10.00"), received_on=date(2026, 8, 1), reference="MANUAL"),
            Receipt(source_key="recharge:R1", channel="wechat_pay", amount=Decimal("20.00"), received_on=date(2026, 4, 2), reference="R1"),
            Receipt(source_key="reservation:S2", channel="wechat_pay", amount=Decimal("17.00"), received_on=date(2026, 11, 13), reference="S2"),
            Receipt(source_key="manual:lgd", channel="wechat_transfer", amount=Decimal("3.00"), received_on=date(2026, 8, 2), reference="LGD-MANUAL", store_id=2),
        ])
        self.db.commit()

        def totals(month=None, store_id=None):
            params = {"year": 2026}
            if month:
                params["month"] = month
            if store_id:
                params["store_id"] = store_id
            data = self.client.get("/admin/receipts/summary", params=params).json()["data"]
            return data["month"] if month else data["year"]

        # 回填前，空门店的核销、手工和充值不进千峰南路；理工大店预约仍在本店。
        self.assertEqual(Decimal(totals(11, 1)["received"]), Decimal("62.70"))
        self.assertEqual(Decimal(totals(11, 2)["received"]), Decimal("17.00"))
        before_all = totals()
        self.assertEqual(Decimal(before_all["received"]), Decimal("182.70"))
        self.assertEqual(Decimal(before_all["refunded"]), Decimal("10.00"))
        self.assertEqual(Decimal(before_all["net"]), Decimal("172.70"))

        stats = backfill_receipt_stores(self.db)
        self.assertEqual(stats["orders_assigned"], 1)
        self.assertEqual(stats["receipts_from_orders"], 3)
        self.assertEqual(stats["receipts_legacy"], 2)
        self.assertEqual(stats["legacy_store_id"], 1)
        again = backfill_receipt_stores(self.db)
        self.assertEqual((again["orders_assigned"], again["receipts_from_orders"], again["receipts_legacy"]), (0, 0, 0))

        self.db.refresh(unscoped)
        self.db.refresh(kept)
        self.db.refresh(pending)
        self.assertEqual(unscoped.store_id, 1)
        self.assertEqual(kept.store_id, 2)
        self.assertIsNone(pending.store_id)
        by_ref = {row.reference: row.store_id for row in self.db.scalars(select(Receipt)).all()}
        self.assertEqual(by_ref, {"S1": 1, "MONTH": 1, "MANUAL": 1, "R1": 1, "S2": 2, "LGD-MANUAL": 2})

        store1, store2 = totals(store_id=1), totals(store_id=2)
        after_all = totals()
        self.assertEqual(after_all, before_all)
        self.assertEqual(Decimal(store1["received"]), Decimal("162.70"))
        self.assertEqual(Decimal(store1["refunded"]), Decimal("10.00"))
        self.assertEqual(Decimal(store1["net"]), Decimal("152.70"))
        self.assertEqual(Decimal(store2["received"]), Decimal("20.00"))
        self.assertEqual(Decimal(store2["refunded"]), Decimal("0"))
        self.assertEqual(Decimal(store1["received"]) + Decimal(store2["received"]), Decimal(after_all["received"]))
        self.assertEqual(Decimal(store1["refunded"]) + Decimal(store2["refunded"]), Decimal(after_all["refunded"]))
        self.assertEqual(Decimal(store1["net"]) + Decimal(store2["net"]), Decimal(after_all["net"]))
        self.assertEqual(Decimal(totals(11, 1)["received"]), Decimal("112.70"))
        self.assertEqual(Decimal(totals(11, 2)["received"]), Decimal("17.00"))
        listed = self.client.get("/admin/receipts", params={"year": 2026, "store_id": 1, "page_size": 100}).json()["data"]
        self.assertEqual({item["reference"] for item in listed["items"]}, {"S1", "MONTH", "MANUAL", "R1"})
        everyone = self.client.get("/admin/receipts", params={"year": 2026, "page_size": 100}).json()["data"]
        self.assertEqual(everyone["total"], 6)

    def test_backfill_stops_when_qianfeng_store_is_missing(self):
        from datetime import date
        from app.models.receipts import Receipt
        from app.services.receipt_store_backfill import backfill_receipt_stores
        self.db.delete(self.db.get(Store, 1))
        self.db.add(Receipt(
            source_key="manual:x", channel="wechat_transfer", amount=Decimal("1.00"),
            received_on=date(2026, 1, 1), reference="X",
        ))
        self.db.commit()
        with self.assertRaises(RuntimeError):
            backfill_receipt_stores(self.db)
        row = self.db.scalar(select(Receipt).where(Receipt.source_key == "manual:x"))
        self.assertIsNone(row.store_id)


if __name__ == "__main__":
    unittest.main()
