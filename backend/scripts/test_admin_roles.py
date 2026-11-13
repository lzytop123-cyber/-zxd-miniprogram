"""后台总部/店长角色单测。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from fastapi import HTTPException  # noqa: E402
from sqlalchemy import create_engine, select  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.db.session import Base  # noqa: E402
from app.models import AdminUser, Store  # noqa: E402
from app.services.admin_access import (  # noqa: E402
    assert_store_access,
    require_hq,
    scope_store_id,
)
from app.services.schema_migrate import run_schema_migrations  # noqa: E402


engine = create_engine("sqlite://")
SessionLocal = sessionmaker(bind=engine)


class AdminRoleTests(unittest.TestCase):
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
        for model in (AdminUser, Store):
            for row in self.db.scalars(select(model)).all():
                self.db.delete(row)
        self.db.commit()
        self.store_a = Store(name="A店", status=1)
        self.store_b = Store(name="B店", status=1)
        self.db.add_all([self.store_a, self.store_b])
        self.db.flush()
        self.hq = AdminUser(username="hq1", password_hash="x", role="hq", status=1)
        self.mgr = AdminUser(
            username="mgr1",
            password_hash="x",
            role="store",
            store_id=self.store_a.id,
            status=1,
        )
        self.db.add_all([self.hq, self.mgr])
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def test_hq_sees_all_stores_scope(self):
        self.assertIsNone(scope_store_id(self.hq, None))
        self.assertEqual(scope_store_id(self.hq, self.store_b.id), self.store_b.id)

    def test_store_forced_scope(self):
        self.assertEqual(scope_store_id(self.mgr, None), self.store_a.id)
        with self.assertRaises(HTTPException) as ctx:
            scope_store_id(self.mgr, self.store_b.id)
        self.assertEqual(ctx.exception.status_code, 403)

    def test_assert_store_access(self):
        assert_store_access(self.hq, self.store_b.id)
        assert_store_access(self.mgr, self.store_a.id)
        with self.assertRaises(HTTPException):
            assert_store_access(self.mgr, self.store_b.id)

    def test_require_hq(self):
        require_hq(self.hq)
        with self.assertRaises(HTTPException):
            require_hq(self.mgr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
