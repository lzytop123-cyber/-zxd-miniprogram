"""按门店分结算：账户解析、权益隔离、支付快照 mchid。"""

from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

# 使用临时 SQLite，避免污染开发库
from sqlalchemy import create_engine, select  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.db.session import Base  # noqa: E402
from app.models import (  # noqa: E402
    BillType,
    CardType,
    PayAccount,
    PayType,
    PeriodCard,
    PricingRule,
    Reservation,
    Seat,
    Store,
    User,
    Zone,
)
from app.services.card_service import validate_period_card_for_reservation  # noqa: E402
from app.services.pay_account import resolve_pay_account  # noqa: E402
from app.services.schema_migrate import run_schema_migrations  # noqa: E402
from app.services.wechat_pay import WechatPayService  # noqa: E402


engine = create_engine("sqlite://")
SessionLocal = sessionmaker(bind=engine)


class PerStoreSettlementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine)
        db = SessionLocal()
        try:
            run_schema_migrations(db)
            db.commit()
        finally:
            db.close()

    def setUp(self):
        self.db = SessionLocal()
        self._cleanup()

    def tearDown(self):
        self._cleanup()
        self.db.close()

    def _cleanup(self):
        for model in (Reservation, PeriodCard, PricingRule, Seat, Zone, Store, PayAccount, User):
            for row in self.db.scalars(select(model)).all():
                self.db.delete(row)
        self.db.commit()

    def _store(self, **kwargs) -> Store:
        kwargs.setdefault("name", "店A")
        kwargs.setdefault("status", 1)
        kwargs.setdefault("benefits_isolated", 0)
        s = Store(**kwargs)
        self.db.add(s)
        self.db.flush()
        return s

    def test_resolve_default_when_unbound(self):
        store = self._store()
        self.db.commit()
        with patch.object(settings, "wx_pay_mchid", "MCH_DEFAULT"):
            acc = resolve_pay_account(self.db, store)
        self.assertEqual(acc.source, "default")
        self.assertEqual(acc.mchid, "MCH_DEFAULT")

    def test_resolve_bound_account(self):
        pay = PayAccount(
            name="新对公",
            mchid="MCH_NEW",
            serial_no="SER",
            api_v3_key="k" * 32,
            key_path="./certs/key.pem",
            status=1,
        )
        self.db.add(pay)
        self.db.flush()
        store = self._store(pay_account_id=pay.id)
        self.db.commit()
        acc = resolve_pay_account(self.db, store)
        self.assertEqual(acc.source, "bound")
        self.assertEqual(acc.mchid, "MCH_NEW")

    def test_bound_incomplete_no_fallback(self):
        pay = PayAccount(
            name="残缺",
            mchid="MCH_BAD",
            serial_no="",
            api_v3_key="",
            key_path="",
            status=1,
        )
        self.db.add(pay)
        self.db.flush()
        store = self._store(pay_account_id=pay.id)
        self.db.commit()
        with self.assertRaises(ValueError):
            resolve_pay_account(self.db, store)

    def test_isolated_rejects_null_store_card(self):
        store = self._store(benefits_isolated=1)
        user = User(openid="o_test_iso", nickname="t")
        self.db.add(user)
        self.db.flush()
        card = PeriodCard(
            user_id=user.id,
            store_id=None,
            card_name="老卡",
            card_type=CardType.daily,
            status=1,
        )
        self.db.add(card)
        self.db.commit()
        start = datetime.now().replace(hour=10, minute=0, second=0, microsecond=0)
        end = start + timedelta(hours=8)
        with self.assertRaises(ValueError) as ctx:
            validate_period_card_for_reservation(
                self.db, card, BillType.daily, start, end, store.id
            )
        self.assertIn("本店", str(ctx.exception))

    def test_mock_pay_snapshots_bound_mchid(self):
        pay = PayAccount(
            name="新对公",
            mchid="MCH_NEW2",
            serial_no="SER",
            api_v3_key="k" * 32,
            key_path="./certs/key.pem",
            status=1,
        )
        self.db.add(pay)
        self.db.flush()
        store = self._store(pay_account_id=pay.id)
        self.db.commit()
        acc = resolve_pay_account(self.db, store)
        params = WechatPayService.create_jsapi_order(
            "ORDTEST1",
            Decimal("1.00"),
            "openid",
            "test",
            pay_account=acc,
        )
        self.assertEqual(params.get("mchid"), "MCH_NEW2")
        self.assertIn("mock_prepay", params["package"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
