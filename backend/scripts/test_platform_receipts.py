"""平台核销收款：真实 SQLite/API，原价不得作为实付自动入账。"""
from datetime import datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import select

import unittest
import test_receipts as base_tests
from app.models import CardSource, CardType, MeituanOrder, MeituanOrderStatus, PeriodCard
from app.models.receipts import Receipt


class PlatformReceiptsTests(unittest.TestCase):
    setUp = base_tests.ReceiptsTests.setUp
    tearDown = base_tests.ReceiptsTests.tearDown
    receipt = base_tests.ReceiptsTests.receipt
    refund = base_tests.ReceiptsTests.refund
    summary = base_tests.ReceiptsTests.summary
    def order(self, channel="meituan", raw=None, **changes):
        code = str(uuid4())
        values = dict(coupon_code=code, user_id=1, status=MeituanOrderStatus.verified, verified_at=datetime(2025, 9, 2), deal_name="月卡", deal_price=Decimal("99"), meituan_raw=raw or {})
        values.update(changes)
        row = MeituanOrder(**values)
        self.db.add(row)
        if channel:
            self.db.add(PeriodCard(user_id=1, card_type=CardType.monthly, source=CardSource(channel), meituan_receipt=code))
        self.db.commit()
        return row

    def sync_platforms(self):
        res = self.client.post("/admin/receipts/sync")
        self.assertEqual(res.status_code, 200, res.text)
        return res.json()["data"]

    def pending(self):
        res = self.client.get("/admin/receipts/platform-review")
        self.assertEqual(res.status_code, 200, res.text)
        return res.json()["data"]

    def confirm(self, order, **changes):
        body = dict(channel="meituan", amount="39.00", received_on="2025-09-02", confirmed=True)
        body.update(changes)
        return self.client.post(f"/admin/receipts/platform-review/{order.id}/confirm", json=body)

    def test_verified_paid_amounts_sync_once_and_ignore_pending(self):
        mt = self.order(raw={"payAmount": 3900, "ticketData": {"dealPrice": 99}})
        dy = self.order("douyin", {"platform": "douyin_official", "ticketData": {"amount": {"pay_amount": 1990, "original_amount": 9990}}})
        self.order(raw={"payAmount": 5000}, status=MeituanOrderStatus.pending)
        for _ in range(2):
            self.sync_platforms()
        self.assertEqual(self.summary(9)["month"]["received"], "58.90")
        self.assertEqual(self.pending()["total"], 0)
        rows = self.db.scalars(select(Receipt)).all()
        self.assertEqual(len(rows), 2)
        self.assertEqual({r.reference for r in rows}, {mt.coupon_code, dy.coupon_code})

    def test_reference_prices_and_zero_never_fall_back_to_original(self):
        self.order(raw={"ticketData": {"dealPrice": 99}})
        self.order("douyin", {"ticketData": {"amount": {"pay_amount": 0, "original_amount": 9900}}})
        self.order("douyin", {"raw_prepare": {"certificates": [{"sku": {"market_price": 9900}}]}})
        self.sync_platforms()
        self.assertEqual(self.summary(9)["month"]["received"], "0.00")
        self.assertEqual(self.pending()["total"], 3)
        self.assertEqual(self.summary(9)["platforms_to_review"], 3)

    def test_confirm_price_then_refund_and_sync_preserve_manual_confirmation(self):
        order = self.order(raw={"ticketData": {"dealPrice": 99}})
        self.sync_platforms()
        res = self.confirm(order)
        self.assertEqual(res.status_code, 200, res.text)
        receipt_id = res.json()["data"]["id"]
        self.assertEqual(self.confirm(order).json()["data"]["id"], receipt_id)
        self.assertEqual(self.confirm(order, amount="40").status_code, 409)
        self.assertEqual(self.refund(receipt_id, amount="9", refunded_on="2025-10-01").status_code, 200)
        self.sync_platforms()
        self.assertEqual(self.pending()["total"], 0)
        self.assertEqual(self.summary(9)["month"]["net"], "39.00")
        self.assertEqual(self.summary(10)["month"]["net"], "-9.00")

    def test_unknown_channel_requires_confirmation_not_default_meituan(self):
        order = self.order(None, {"platform": "yunlaoban", "payAmount": 3900})
        self.sync_platforms()
        item = self.pending()["items"][0]
        self.assertIsNone(item["channel"])
        self.assertEqual(self.confirm(order, channel="douyin").status_code, 200)
        self.assertEqual(self.summary(9)["month"]["received"], "39.00")

    def test_manual_reference_collision_requires_link_not_duplicate(self):
        order = self.order(raw={"payAmount": 3900})
        manual = self.receipt(channel="meituan", amount="39", received_on="2025-09-02", reference=order.coupon_code)
        self.sync_platforms()
        self.assertEqual(self.pending()["total"], 1)
        self.assertEqual(self.summary(9)["month"]["received"], "39.00")
        self.assertEqual(self.confirm(order).status_code, 409)
        res = self.confirm(order, existing_receipt_id=manual["id"])
        self.assertEqual(res.status_code, 200, res.text)
        self.assertEqual(res.json()["data"]["id"], manual["id"])
        self.sync_platforms()
        self.assertEqual(self.pending()["total"], 0)
        self.assertEqual(self.summary(9)["month"]["received"], "39.00")

    def test_refunded_platform_still_counts_original_receipt_and_flags_review(self):
        order = self.order("douyin", {"platform": "douyin_official", "ticketData": {"amount": {"pay_amount": 3900}}})
        self.sync_platforms()
        order.status = MeituanOrderStatus.refunded
        self.db.commit()
        self.sync_platforms()
        self.assertEqual(self.summary(9)["month"]["received"], "39.00")
        self.assertEqual(self.summary(9)["refunds_to_review"], 1)

    def test_missing_date_and_conflicting_prices_require_review(self):
        self.order(raw={"payAmount": 3900}, verified_at=None)
        self.order("douyin", {"payAmount": 3900, "ticketData": {"amount": {"pay_amount": 4900}}})
        self.order(raw={"payAmount": "NaN"})
        self.sync_platforms()
        self.assertEqual(self.pending()["total"], 3)
        self.assertEqual(self.summary(9)["month"]["received"], "0.00")

    def test_multiple_certificates_and_time_cards_require_allocation_review(self):
        self.order("douyin", {"ticketData": {"amount": {"pay_amount": 9900}}, "raw_prepare": {"certificates": [{"amount": {"pay_amount": 9900}}, {"amount": {"pay_amount": 9900}}]}})
        self.order("douyin", {"raw_prepare": {"certificate": {"amount": {"pay_amount": 9900}, "time_card": {"serial_amount_list": [{"amount": {"pay_amount": 3300}}]}}}})
        self.sync_platforms()
        self.assertEqual(self.pending()["total"], 2)
        self.assertEqual(self.summary(9)["month"]["received"], "0.00")

    def test_source_snapshot_works_without_card_and_conflicting_source_is_pending(self):
        self.order(None, {"receipt_channel": "meituan", "payAmount": 3900})
        self.order("douyin", {"receipt_channel": "meituan", "payAmount": 4900})
        self.sync_platforms()
        self.assertEqual(self.summary(9)["month"]["received"], "39.00")
        self.assertIsNone(self.pending()["items"][0]["channel"])

    def test_bulk_reconcile_links_and_inserts_reference_price(self):
        # A: reference price only, channel + date known → should insert at reference_price.
        a = self.order(deal_price=Decimal("99"))
        # B: manual receipt matches → should link, not double-insert.
        b = self.order(deal_price=Decimal("88"))
        manual = self.receipt(channel="meituan", amount="88", received_on="2025-09-02", reference=b.coupon_code)
        # C: unknown channel → must skip; safety hasn't changed.
        c = self.order(None, {"platform": "yunlaoban"}, deal_price=Decimal("77"))
        self.sync_platforms()
        res = self.client.post("/admin/receipts/platform-review/bulk-reconcile")
        self.assertEqual(res.status_code, 200, res.text)
        self.assertEqual(res.json()["data"], {"linked": 1, "inserted": 1, "skipped": 1})
        self.assertEqual(self.summary(9)["month"]["received"], f"{99 + 88}.00")
        self.assertEqual(self.pending()["total"], 1)
        rows = self.db.scalars(select(Receipt)).all()
        self.assertEqual({r.reference for r in rows}, {a.coupon_code, b.coupon_code})
        self.assertEqual(next(r for r in rows if r.reference == b.coupon_code).id, manual["id"])
        # Idempotent: running again does nothing.
        self.assertEqual(self.client.post("/admin/receipts/platform-review/bulk-reconcile").json()["data"], {"linked": 0, "inserted": 0, "skipped": 1})
        # Auth check.
        from app.api.deps import get_current_admin
        self.app.dependency_overrides.pop(get_current_admin)
        self.assertEqual(self.client.post("/admin/receipts/platform-review/bulk-reconcile").status_code, 401)
        self.assertEqual(c.id, c.id)  # keep reference alive

    def test_confirmation_validation_and_authentication(self):
        from app.api.deps import get_current_admin
        order = self.order(raw={"ticketData": {"dealPrice": 99}})
        self.assertEqual(self.confirm(order, channel="douyin").status_code, 400)
        self.assertEqual(self.confirm(order, amount="0").status_code, 422)
        self.assertEqual(self.confirm(order, confirmed=False).status_code, 422)
        self.assertEqual(self.confirm(order, received_on="2099-01-01").status_code, 400)
        self.app.dependency_overrides.pop(get_current_admin)
        self.assertEqual(self.client.post("/admin/receipts/sync").status_code, 401)
        self.assertEqual(self.client.get("/admin/receipts/platform-review").status_code, 401)
        self.assertEqual(self.confirm(order).status_code, 401)
