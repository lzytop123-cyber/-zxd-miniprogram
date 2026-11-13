"""后台店长模块权限守卫（补充各路由内的门店过滤）。"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.core.security import decode_access_token
from app.db.session import SessionLocal
from app.models import AdminUser
from app.services.admin_access import is_hq
from app.services.admin_permissions import has_permission, module_for_admin_path


def _is_hard_denied(method: str, path: str) -> bool:
    """店长即使勾选对应模块也不可放行的操作。"""
    method = method.upper()
    if path.rstrip("/") == "/api/admin/stores" and method == "POST":
        return True
    if "/pricing/copy-to/" in path:
        return True
    if path == "/api/admin/pay-accounts" or path.startswith("/api/admin/pay-accounts/"):
        if method in ("POST", "PUT", "PATCH", "DELETE"):
            return True
    if path.rstrip("/") == "/api/admin/system/migrate" and method == "POST":
        return True
    return False


def _load_admin(request: Request) -> AdminUser | JSONResponse:
    auth = request.headers.get("authorization") or ""
    if not auth.lower().startswith("bearer "):
        return JSONResponse({"code": 401, "message": "未登录", "data": None}, status_code=401)
    subject = decode_access_token(auth.split(" ", 1)[1].strip())
    if not subject or not subject.startswith("admin:"):
        return JSONResponse({"code": 401, "message": "无效令牌", "data": None}, status_code=401)
    try:
        admin_id = int(subject.split(":")[1])
    except ValueError:
        return JSONResponse({"code": 401, "message": "无效令牌", "data": None}, status_code=401)

    db = SessionLocal()
    try:
        admin = db.get(AdminUser, admin_id)
        if not admin or admin.status != 1:
            return JSONResponse({"code": 401, "message": "管理员不存在", "data": None}, status_code=401)
        # Detach identity for use after session close.
        db.expunge(admin)
        return admin
    finally:
        db.close()


class AdminRoleGuardMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if not path.startswith("/api/admin"):
            return await call_next(request)
        if path in ("/api/admin/login", "/api/admin/me"):
            return await call_next(request)
        # Browser CORS preflight has no Bearer token; never auth-check OPTIONS.
        if request.method == "OPTIONS":
            return await call_next(request)

        method = request.method
        hard_deny = _is_hard_denied(method, path)
        module = module_for_admin_path(method, path)
        if module is None and not hard_deny:
            return await call_next(request)

        admin_or_error = _load_admin(request)
        if isinstance(admin_or_error, JSONResponse):
            return admin_or_error
        admin = admin_or_error

        if is_hq(admin):
            return await call_next(request)

        if hard_deny:
            return JSONResponse(
                {"code": 403, "message": "需要总部权限", "data": None},
                status_code=403,
            )
        if module is not None and not has_permission(admin, module):
            return JSONResponse(
                {"code": 403, "message": "无此模块权限", "data": None},
                status_code=403,
            )
        return await call_next(request)
