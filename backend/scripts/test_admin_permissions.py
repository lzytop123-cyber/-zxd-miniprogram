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
        try:
            os.remove(db_path)
        except OSError:
            pass


def _run_isolated_case(env_key: str, case: str) -> None:
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    env = os.environ.copy()
    env.pop("ADMIN_PERM_MIGRATION_TEST", None)
    env.pop("ADMIN_PERM_GUARD_TEST", None)
    env.pop("ADMIN_PERM_CRUD_TEST", None)
    env["DATABASE_URL"] = f"sqlite:///{db_path}"
    env["APP_ENV"] = "development"
    env[env_key] = case
    result = subprocess.run(
        [sys.executable, str(Path(__file__).resolve())],
        env=env,
        cwd=str(BACKEND),
        capture_output=True,
        text=True,
    )
    try:
        os.remove(db_path)
    except OSError:
        pass
    if result.returncode != 0:
        raise AssertionError(result.stdout + result.stderr)


class GuardMiddlewareTests(unittest.TestCase):
    """API 守卫：模块权限 + 硬限制（子进程 + 独立 SQLite，避免污染 test_admin_roles）。"""

    def _run_guard_case(self, case: str) -> None:
        _run_isolated_case("ADMIN_PERM_GUARD_TEST", case)

    def test_store_without_receipts_forbidden(self):
        self._run_guard_case("store_without_receipts_forbidden")

    def test_store_defaults_can_stats(self):
        self._run_guard_case("store_defaults_can_stats")

    def test_store_with_banners_allowed(self):
        self._run_guard_case("store_with_banners_allowed")

    def test_store_cannot_create_store(self):
        self._run_guard_case("store_cannot_create_store")

    def test_store_cannot_copy_pricing(self):
        self._run_guard_case("store_cannot_copy_pricing")

    def test_store_cannot_post_pay_accounts_even_with_permission(self):
        self._run_guard_case("store_cannot_post_pay_accounts_even_with_permission")

    def test_hq_former_hq_only_still_ok(self):
        self._run_guard_case("hq_former_hq_only_still_ok")


class AdminCrudPermissionTests(unittest.TestCase):
    """登录/me/创建/更新管理员权限（子进程隔离）。"""

    def _run_crud_case(self, case: str) -> None:
        _run_isolated_case("ADMIN_PERM_CRUD_TEST", case)

    def test_create_store_default_permissions(self):
        self._run_crud_case("create_store_default_permissions")

    def test_create_store_custom_permissions(self):
        self._run_crud_case("create_store_custom_permissions")

    def test_me_returns_permissions(self):
        self._run_crud_case("me_returns_permissions")

    def test_list_includes_permission_summary(self):
        self._run_crud_case("list_includes_permission_summary")

    def test_patch_updates_permissions(self):
        self._run_crud_case("patch_updates_permissions")

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


def _build_guard_app():
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
        store_id = store.id
        hq = AdminUser(username="guard_hq", password_hash="x", role="hq", status=1)
        store_default = AdminUser(
            username="guard_store_default",
            password_hash="x",
            role="store",
            store_id=store.id,
            status=1,
            permissions=None,
        )
        store_no_receipts = AdminUser(
            username="guard_store_no_receipts",
            password_hash="x",
            role="store",
            store_id=store.id,
            status=1,
            permissions=["dashboard", "stores", "pricing"],
        )
        store_with_banners = AdminUser(
            username="guard_store_banners",
            password_hash="x",
            role="store",
            store_id=store.id,
            status=1,
            permissions=list(STORE_DEFAULT_PERMISSIONS) + ["banners"],
        )
        store_with_pay_accounts = AdminUser(
            username="guard_store_pay_accounts",
            password_hash="x",
            role="store",
            store_id=store.id,
            status=1,
            permissions=list(STORE_DEFAULT_PERMISSIONS) + ["pay_accounts"],
        )
        db.add_all(
            [
                hq,
                store_default,
                store_no_receipts,
                store_with_banners,
                store_with_pay_accounts,
            ]
        )
        db.commit()
        for admin in (
            hq,
            store_default,
            store_no_receipts,
            store_with_banners,
            store_with_pay_accounts,
        ):
            db.refresh(admin)
    finally:
        db.close()

    stub = APIRouter()
    current_admin_holder: dict[str, AdminUser | None] = {"admin": hq}

    @stub.get("/admin/stats", response_model=ResponseModel)
    def stub_stats(_: object = Depends(get_current_admin)):
        return ResponseModel(data={"ok": True})

    @stub.get("/admin/banners", response_model=ResponseModel)
    def stub_banners(_: object = Depends(get_current_admin)):
        return ResponseModel(data=[])

    @stub.post("/admin/stores", response_model=ResponseModel)
    def stub_create_store(_: object = Depends(get_current_admin)):
        return ResponseModel(data={"id": 1})

    @stub.post("/admin/pay-accounts", response_model=ResponseModel)
    def stub_create_pay_account(_: object = Depends(get_current_admin)):
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

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_admin] = lambda: current_admin_holder["admin"]

    client = TestClient(app)

    def auth(admin: AdminUser) -> dict[str, str]:
        current_admin_holder["admin"] = admin
        token = create_access_token(f"admin:{admin.id}")
        return {"Authorization": f"Bearer {token}"}

    return {
        "client": client,
        "auth": auth,
        "store_id": store_id,
        "hq": hq,
        "store_default": store_default,
        "store_no_receipts": store_no_receipts,
        "store_with_banners": store_with_banners,
        "store_with_pay_accounts": store_with_pay_accounts,
    }


def _run_guard_test(case: str) -> None:
    ctx = _build_guard_app()
    client = ctx["client"]
    auth = ctx["auth"]
    try:
        if case == "store_without_receipts_forbidden":
            res = client.get(
                "/api/admin/receipts/summary",
                params={"year": 2025},
                headers=auth(ctx["store_no_receipts"]),
            )
            assert res.status_code == 403, res.text
            assert res.json()["message"] == "无此模块权限"
        elif case == "store_defaults_can_stats":
            res = client.get("/api/admin/stats", headers=auth(ctx["store_default"]))
            assert res.status_code == 200, res.text
        elif case == "store_with_banners_allowed":
            res = client.get("/api/admin/banners", headers=auth(ctx["store_with_banners"]))
            assert res.status_code == 200, res.text
        elif case == "store_cannot_create_store":
            res = client.post("/api/admin/stores", headers=auth(ctx["store_default"]), json={})
            assert res.status_code == 403, res.text
        elif case == "store_cannot_copy_pricing":
            res = client.post(
                f"/api/admin/stores/{ctx['store_id']}/pricing/copy-to/99",
                headers=auth(ctx["store_default"]),
            )
            assert res.status_code == 403, res.text
        elif case == "store_cannot_post_pay_accounts_even_with_permission":
            res = client.post(
                "/api/admin/pay-accounts",
                headers=auth(ctx["store_with_pay_accounts"]),
                json={"name": "x", "mchid": "1", "serial_no": "1", "api_v3_key": "k", "key_path": "/k"},
            )
            assert res.status_code == 403, res.text
            assert res.json()["message"] == "需要总部权限"
        elif case == "hq_former_hq_only_still_ok":
            res = client.get("/api/admin/banners", headers=auth(ctx["hq"]))
            assert res.status_code == 200, res.text
        else:
            raise AssertionError(f"unknown guard case: {case}")
    finally:
        client.close()


def _build_crud_app():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from sqlalchemy import select

    from app.api.admin_role_guard import AdminRoleGuardMiddleware
    from app.api.routes import admin as admin_routes
    from app.core.security import hash_password
    from app.db.session import Base, SessionLocal, engine, get_db
    from app.models import AdminUser, Store
    from app.services.admin_permissions import permission_summary
    from app.services.schema_migrate import run_schema_migrations

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        for model in (AdminUser, Store):
            for row in db.scalars(select(model)).all():
                db.delete(row)
        db.commit()
        run_schema_migrations(db)
        db.commit()
        store = Store(name="CRUD测店", status=1)
        db.add(store)
        db.flush()
        hq = AdminUser(
            username="crud_hq",
            password_hash=hash_password("hq-pass-1"),
            role="hq",
            status=1,
            permissions=None,
        )
        store_admin = AdminUser(
            username="crud_store",
            password_hash=hash_password("store-pass-1"),
            role="store",
            store_id=store.id,
            status=1,
            permissions=None,
        )
        db.add_all([hq, store_admin])
        db.commit()
        db.refresh(hq)
        db.refresh(store_admin)
        store_id = store.id
        hq_id = hq.id
        store_admin_id = store_admin.id
    finally:
        db.close()

    app = FastAPI()
    app.add_middleware(AdminRoleGuardMiddleware)
    app.include_router(admin_routes.router, prefix="/api")

    def _override_db():
        session = SessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = _override_db
    client = TestClient(app)
    return {
        "client": client,
        "store_id": store_id,
        "hq_id": hq_id,
        "store_admin_id": store_admin_id,
        "permission_summary": permission_summary,
    }


def _hq_headers(client) -> dict[str, str]:
    res = client.post(
        "/api/admin/login",
        json={"username": "crud_hq", "password": "hq-pass-1"},
    )
    assert res.status_code == 200, res.text
    token = res.json()["data"]["token"]
    return {"Authorization": f"Bearer {token}"}


def _run_crud_test(case: str) -> None:
    from sqlalchemy import select

    from app.db.session import SessionLocal
    from app.models import AdminUser

    ctx = _build_crud_app()
    client = ctx["client"]
    try:
        headers = _hq_headers(client)
        if case == "create_store_default_permissions":
            res = client.post(
                "/api/admin/admins",
                headers=headers,
                json={
                    "username": "new_store_default",
                    "password": "pass1234",
                    "role": "store",
                    "store_id": ctx["store_id"],
                },
            )
            assert res.status_code == 200, res.text
            data = res.json()["data"]
            assert data["permissions"] == list(STORE_DEFAULT_PERMISSIONS), data
            db = SessionLocal()
            try:
                row = db.scalar(select(AdminUser).where(AdminUser.username == "new_store_default"))
                assert row is not None
                assert row.permissions == list(STORE_DEFAULT_PERMISSIONS)
            finally:
                db.close()
        elif case == "create_store_custom_permissions":
            res = client.post(
                "/api/admin/admins",
                headers=headers,
                json={
                    "username": "new_store_custom",
                    "password": "pass1234",
                    "role": "store",
                    "store_id": ctx["store_id"],
                    "permissions": ["dashboard", "not_a_real_module"],
                },
            )
            assert res.status_code == 200, res.text
            data = res.json()["data"]
            assert data["permissions"] == ["dashboard"], data
            db = SessionLocal()
            try:
                row = db.scalar(select(AdminUser).where(AdminUser.username == "new_store_custom"))
                assert row is not None
                assert row.permissions == ["dashboard"]
            finally:
                db.close()
        elif case == "me_returns_permissions":
            login = client.post(
                "/api/admin/login",
                json={"username": "crud_store", "password": "store-pass-1"},
            )
            assert login.status_code == 200, login.text
            login_data = login.json()["data"]
            assert login_data["permissions"] == list(STORE_DEFAULT_PERMISSIONS), login_data
            me = client.get(
                "/api/admin/me",
                headers={"Authorization": f"Bearer {login_data['token']}"},
            )
            assert me.status_code == 200, me.text
            me_data = me.json()["data"]
            assert me_data["permissions"] == list(STORE_DEFAULT_PERMISSIONS), me_data
            hq_me = client.get("/api/admin/me", headers=headers)
            assert hq_me.status_code == 200, hq_me.text
            hq_perms = hq_me.json()["data"]["permissions"]
            assert "admins" in hq_perms
            assert len(hq_perms) == len(normalize_permissions("hq", None))
        elif case == "list_includes_permission_summary":
            res = client.get("/api/admin/admins", headers=headers)
            assert res.status_code == 200, res.text
            items = res.json()["data"]
            by_user = {i["username"]: i for i in items}
            store_item = by_user["crud_store"]
            assert store_item["permissions"] == list(STORE_DEFAULT_PERMISSIONS)
            assert store_item["permission_summary"] == ctx["permission_summary"](
                list(STORE_DEFAULT_PERMISSIONS)
            )
            hq_item = by_user["crud_hq"]
            assert "admins" in hq_item["permissions"]
            assert hq_item["permission_summary"]
        elif case == "patch_updates_permissions":
            res = client.patch(
                f"/api/admin/admins/{ctx['store_admin_id']}",
                headers=headers,
                json={"permissions": ["dashboard", "receipts"]},
            )
            assert res.status_code == 200, res.text
            data = res.json()["data"]
            assert data["permissions"] == ["dashboard", "receipts"], data
            db = SessionLocal()
            try:
                row = db.get(AdminUser, ctx["store_admin_id"])
                assert row is not None
                assert row.permissions == ["dashboard", "receipts"]
            finally:
                db.close()
            listed = client.get("/api/admin/admins", headers=headers)
            item = next(i for i in listed.json()["data"] if i["id"] == ctx["store_admin_id"])
            assert item["permission_summary"] == "2项"
        else:
            raise AssertionError(f"unknown crud case: {case}")
    finally:
        client.close()


if __name__ == "__main__":
    guard_case = os.environ.get("ADMIN_PERM_GUARD_TEST")
    crud_case = os.environ.get("ADMIN_PERM_CRUD_TEST")
    if guard_case:
        _run_guard_test(guard_case)
    elif crud_case:
        _run_crud_test(crud_case)
    elif os.environ.get("ADMIN_PERM_MIGRATION_TEST") == "1":
        _run_migration_test()
    else:
        unittest.main()