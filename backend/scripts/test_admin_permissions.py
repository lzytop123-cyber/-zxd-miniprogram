"""后台模块权限目录单测。"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.services.admin_permissions import (  # noqa: E402
    STORE_DEFAULT_PERMISSIONS,
    normalize_permissions,
    module_for_admin_path,
    has_permission,
)


class PermissionCatalogTests(unittest.TestCase):
    def test_null_store_gets_defaults(self):
        self.assertEqual(normalize_permissions("store", None), list(STORE_DEFAULT_PERMISSIONS))

    def test_empty_store_gets_none(self):
        self.assertEqual(normalize_permissions("store", []), [])

    def test_hq_ignores_raw(self):
        self.assertIn("admins", normalize_permissions("hq", []))

    def test_path_maps_receipts(self):
        self.assertEqual(module_for_admin_path("GET", "/api/admin/receipts/summary"), "receipts")

    def test_path_maps_store_expiring_cards_to_live_board(self):
        self.assertEqual(
            module_for_admin_path("GET", "/api/admin/stores/1/expiring-cards"),
            "live_board",
        )

    def test_unknown_admin_path_returns_none(self):
        self.assertIsNone(module_for_admin_path("GET", "/api/admin/login"))


class PermissionsMigrationTests(unittest.TestCase):
    def test_create_all_migrate_backfill(self):
        fd, db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        env = os.environ.copy()
        env["DATABASE_URL"] = f"sqlite:///{db_path}"
        env["APP_ENV"] = "development"
        env["ADMIN_PERM_MIGRATION_TEST"] = "1"
        result = subprocess.run(
            [sys.executable, str(Path(__file__).resolve())],
            env=env,
            cwd=str(BACKEND),
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


def _run_migration_test() -> None:
    from sqlalchemy import inspect, select

    from app.db.session import Base, SessionLocal, engine
    from app.models import AdminUser, Store
    from app.services.schema_migrate import run_schema_migrations

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        store = Store(name="迁移测店", status=1)
        db.add(store)
        db.flush()
        db.add_all(
            [
                AdminUser(
                    username="perm_hq",
                    password_hash="x",
                    role="hq",
                    status=1,
                    permissions=None,
                ),
                AdminUser(
                    username="perm_store",
                    password_hash="x",
                    role="store",
                    store_id=store.id,
                    status=1,
                    permissions=None,
                ),
            ]
        )
        db.commit()
        run_schema_migrations(db)
        db.commit()

        cols = {c["name"] for c in inspect(engine).get_columns("admin_users")}
        assert "permissions" in cols, "permissions column missing"

        store_admin = db.scalar(select(AdminUser).where(AdminUser.username == "perm_store"))
        hq_admin = db.scalar(select(AdminUser).where(AdminUser.username == "perm_hq"))
        assert store_admin is not None
        assert store_admin.permissions == list(STORE_DEFAULT_PERMISSIONS)
        assert hq_admin is not None and hq_admin.permissions is None
        assert normalize_permissions(store_admin.role, store_admin.permissions) == list(
            STORE_DEFAULT_PERMISSIONS
        )
        assert has_permission(store_admin, "receipts")
    finally:
        db.close()


if __name__ == "__main__":
    if os.environ.get("ADMIN_PERM_MIGRATION_TEST") == "1":
        _run_migration_test()
    else:
        unittest.main()
