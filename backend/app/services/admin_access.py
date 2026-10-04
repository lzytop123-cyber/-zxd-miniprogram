"""后台总部 / 店长权限。"""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select

from app.models import AdminUser, CardPurchaseOrder, MeituanOrder, Reservation

ROLE_HQ = "hq"
ROLE_STORE = "store"


def store_related_user_ids(db, store_id: int) -> set[int]:
    """本店有过预约 / 购卡 / 核销的用户 ID 集合。"""
    sid = int(store_id)
    ids: set[int] = set()
    for model in (Reservation, CardPurchaseOrder, MeituanOrder):
        rows = db.scalars(
            select(model.user_id).where(model.store_id == sid, model.user_id.isnot(None))
        ).all()
        ids.update(int(uid) for uid in rows if uid is not None)
    return ids


def admin_role(admin: AdminUser) -> str:
    role = (getattr(admin, "role", None) or ROLE_HQ).strip() or ROLE_HQ
    return role if role in (ROLE_HQ, ROLE_STORE) else ROLE_HQ


def is_hq(admin: AdminUser) -> bool:
    return admin_role(admin) == ROLE_HQ


def is_store_admin(admin: AdminUser) -> bool:
    return admin_role(admin) == ROLE_STORE


def require_hq(admin: AdminUser) -> None:
    if not is_hq(admin):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要总部权限")


def assert_store_access(admin: AdminUser, store_id: int | None) -> None:
    """店长只能访问自己的门店；总部放行。"""
    if is_hq(admin):
        return
    if not admin.store_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="店长未绑定门店")
    if store_id is None or int(store_id) != int(admin.store_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问其他门店")


def scope_store_id(admin: AdminUser, store_id: int | None = None) -> int | None:
    """
    列表筛选用的门店 ID。
    - 总部：沿用请求参数（可为 None=全部）
    - 店长：强制为本店；若请求其他店则 403
    """
    if is_hq(admin):
        return store_id
    if not admin.store_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="店长未绑定门店")
    if store_id is not None and int(store_id) != int(admin.store_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问其他门店")
    return int(admin.store_id)


def require_store_bound(admin: AdminUser) -> int:
    if is_hq(admin):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="总部账号请指定门店")
    if not admin.store_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="店长未绑定门店")
    return int(admin.store_id)


def assert_store_related_user(db, admin: AdminUser, user_id: int) -> None:
    """店长只能操作本店关联用户；总部放行。"""
    if is_hq(admin):
        return
    related = store_related_user_ids(db, require_store_bound(admin))
    if int(user_id) not in related:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问其他门店用户")
