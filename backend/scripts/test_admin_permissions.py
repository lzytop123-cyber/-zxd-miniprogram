"""后台模块权限目录单测 + API 守卫。"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

_GUARD_DB_PATH: str | None = None
if os.environ.get("ADMIN_PERM_MIGRATION_TEST") != "1":
    _fd, _GUARD_DB_PATH = tempfile.mkstemp(suffix=".db")
    os.close(_fd)
    os.environ["DATABASE_URL"] = f"sqlite:///{_GUARD_DB_PATH}"
    os.environ["APP_ENV"] = "development"

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


class GuardMiddlewareTests(unittest.TestCase):
    """API 守卫：模块权限 + 硬限制（TestClient）。"""

    @classmethod
    def setUpClass(cls):
        from fastapi import APIRouter, Depends, FastAPI
        from fastapi.testclient import TestClient
        from sqlalchemy import select

        from app.api.admin_role_guard import AdminRoleGuardMiddleware
        from app.api.deps import get_current_admin
        from app.api.routes import admin_receipts
        from app.core.security import create_access_token
        from app.db.session import Base, SessionLocal, engine, get_db
        from app.models import AdminUser, Store
        from app.schemas.common import ResponseModel

        Base.metadata.create_all(bind=engine)
        db = SessionLocal()
        try:
            for model in (AdminUser, Store):
                for row in db.scalars(select(model)).all():
                    db.delete(row)
            db.commit()
            store = Store(name="权限测店", status=1)
            db.add(store)
            db.flush()
            cls.store_id = store.id
            cls.hq = AdminUser(username="guard_hq", password_hash="x", role="hq", status=1)
            cls.store_default = AdminUser(
                username="guard_store_default",
                password_hash="x",
                role="store",
                store_id=store.id,
                status=1,
                permissions=None,
            )
            cls.store_no_receipts = AdminUser(
                username="guard_store_no_receipts",
                password_hash="x",
                role="store",
                store_id=store.id,
                status=1,
                permissions=["dashboard", "stores", "pricing"],
            )
            cls.store_with_banners = AdminUser(
                username="guard_store_banners",
                password_hash="x",
                role="store",
                store_id=store.id,
                status=1,
                permissions=list(STORE_DEFAULT_PERMISSIONS) + ["banners"],
            )
            db.add_all([cls.hq, cls.store_default, cls.store_no_receipts, cls.store_with_banners])
            db.commit()
            for admin in (cls.hq, cls.store_default, cls.store_no_receipts, cls.store_with_banners):
                db.refresh(admin)
        finally:
            db.close()

        stub = APIRouter()

        @stub.get("/admin/stats", response_model=ResponseModel)
        def stub_stats(_: object = Depends(get_current_admin)):
            return ResponseModel(data={"ok": True})

        @stub.get("/admin/banners", response_model=ResponseModel)
        def stub_banners(_: object = Depends(get_current_admin)):
            return ResponseModel(data=[])

        @stub.post("/admin/stores", response_model=ResponseModel)
        def stub_create_store(_: object = Depends(get_current_admin)):
            return ResponseModel(data={"id": 1})

        @stub.post(
            "/admin/stores/{source_id}/pricing/copy-to/{target_id}",
            response_model=ResponseModel,
        )
        def stub_copy_pricing(
            source_id: int,
            target_id: int,
            _: object = Depends(get_current_admin),
        ):
            return ResponseModel(data={"source_id": source_id, "target_id": target_id})

        app = FastAPI()
        app.add_middleware(AdminRoleGuardMiddleware)
        app.include_router(admin_receipts.router, prefix="/api")
        app.include_router(stub, prefix="/api")

        def _override_db():
            session = SessionLocal()
            try:
                yield session
            finally:
                session.close()

        # Route deps use whichever admin the test sets on the class.
        app.dependency_overrides[get_db] = _override_db
        app.dependency_overrides[get_current_admin] = lambda: cls._current_admin

        cls.SessionLocal = SessionLocal
        cls.create_access_token = staticmethod(create_access_token)
        cls.client = TestClient(app)
        cls._current_admin = cls.hq

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "client"):
            cls.client.close()
        if _GUARD_DB_PATH:
            try:
                os.remove(_GUARD_DB_PATH)
            except OSError:
                pass

    def _auth(self, admin) -> dict[str, str]:
        self.__class__._current_admin = admin
        token = self.create_access_token(f"admin:{admin.id}")
        return {"Authorization": f"Bearer {token}"}

    def test_store_without_receipts_forbidden(self):
        res = self.client.get(
            "/api/admin/receipts/summary",
            params={"year": 2025},
            headers=self._auth(self.store_no_receipts),
        )
        self.assertEqual(res.status_code, 403, res.text)
        self.assertEqual(res.json()["message"], "无此模块权限")

    def test_store_defaults_can_stats(self):
        res = self.client.get("/api/admin/stats", headers=self._auth(self.store_default))
        self.assertEqual(res.status_code, 200, res.text)

    def test_store_with_banners_allowed(self):
        res = self.client.get("/api/admin/banners", headers=self._auth(self.store_with_banners))
        self.assertEqual(res.status_code, 200, res.text)

    def test_store_cannot_create_store(self):
        res = self.client.post("/api/admin/stores", headers=self._auth(self.store_default), json={})
        self.assertEqual(res.status_code, 403, res.text)

    def test_store_cannot_copy_pricing(self):
        res = self.client.post(
            f"/api/admin/stores/{self.store_id}/pricing/copy-to/99",
            headers=self._auth(self.store_default),
        )
        self.assertEqual(res.status_code, 403, res.text)

    def test_hq_former_hq_only_still_ok(self):
        res = self.client.get("/api/admin/banners", headers=self._auth(self.hq))
        self.assertEqual(res.status_code, 200, res.text)


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
        try:
            unittest.main()
        finally:
            if _GUARD_DB_PATH:
                try:
                    os.remove(_GUARD_DB_PATH)
                except OSError:
                    pass

