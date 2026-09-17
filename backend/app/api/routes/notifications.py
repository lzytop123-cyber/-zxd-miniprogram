"""站内消息中心：后台发/查历史；用户拉取/标记已读。"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin, get_current_user
from app.db.session import get_db
from app.models import AdminUser, Notification, NotificationRead, Store, User
from app.schemas.common import ResponseModel
from app.services.admin_audit import log_admin_action

router = APIRouter(tags=["消息中心"])


class NotificationCreate(BaseModel):
    title: str = Field(..., max_length=100)
    content: str = Field(..., max_length=2000)
    category: Literal["system", "reminder", "promo"] = "system"
    target_type: Literal["all", "user", "store"] = "all"
    target_user_id: int | None = None
    store_id: int | None = None
    link_path: str | None = Field(default=None, max_length=200)


def _serialize(n: Notification) -> dict:
    return {
        "id": n.id,
        "title": n.title,
        "content": n.content,
        "category": n.category,
        "target_type": n.target_type,
        "target_user_id": n.target_user_id,
        "store_id": n.store_id,
        "link_path": n.link_path,
        "created_at": n.created_at.strftime("%Y-%m-%d %H:%M"),
    }


# ============ 后台：发消息 + 查历史 ============

@router.post("/admin/notifications", response_model=ResponseModel)
def send_notification(
    body: NotificationCreate,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    if body.target_type == "user":
        if not body.target_user_id:
            raise HTTPException(status_code=400, detail="指定用户时需提供 target_user_id")
        if not db.get(User, body.target_user_id):
            raise HTTPException(status_code=404, detail="用户不存在")
    if body.target_type == "store":
        if not body.store_id:
            raise HTTPException(status_code=400, detail="门店消息需提供 store_id")
        if not db.get(Store, body.store_id):
            raise HTTPException(status_code=404, detail="门店不存在")
    n = Notification(
        title=body.title.strip(),
        content=body.content.strip(),
        category=body.category,
        target_type=body.target_type,
        target_user_id=body.target_user_id if body.target_type == "user" else None,
        store_id=body.store_id if body.target_type == "store" else None,
        link_path=body.link_path,
        sent_by_admin_id=admin.id,
    )
    db.add(n)
    db.flush()
    log_admin_action(
        db, admin, "send_notification", target_type="notification", target_id=n.id,
        detail=f"{body.target_type}:{body.target_user_id or body.store_id or 'all'}",
    )
    db.commit()
    return ResponseModel(message="消息已发送", data=_serialize(n))


@router.get("/admin/notifications", response_model=ResponseModel)
def list_notifications_admin(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    _: object = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    q = select(Notification).order_by(Notification.id.desc())
    total = db.scalar(select(func.count()).select_from(Notification)) or 0
    rows = db.scalars(q.offset((page - 1) * size).limit(size)).all()
    items = []
    for n in rows:
        item = _serialize(n)
        item["read_count"] = db.scalar(
            select(func.count()).select_from(NotificationRead).where(NotificationRead.notification_id == n.id)
        ) or 0
        items.append(item)
    return ResponseModel(data={"items": items, "total": total, "page": page, "size": size})


# ============ 小程序：拉消息、标记已读、未读数 ============

def _mine_query(user: User):
    """当前用户可见的消息：全体广播 + 门店消息（用户偏好门店）+ 指定给自己的。"""
    conds = [Notification.target_type == "all", Notification.target_user_id == user.id]
    if user.preferred_store_id:
        conds.append(
            (Notification.target_type == "store") & (Notification.store_id == user.preferred_store_id)
        )
    from sqlalchemy import or_
    return select(Notification).where(or_(*conds)).order_by(Notification.id.desc())


@router.get("/notifications/mine", response_model=ResponseModel)
def list_notifications_mine(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = db.scalars(_mine_query(user).offset((page - 1) * size).limit(size)).all()
    read_ids = set(
        db.scalars(
            select(NotificationRead.notification_id).where(
                NotificationRead.user_id == user.id,
                NotificationRead.notification_id.in_([n.id for n in rows] or [0]),
            )
        ).all()
    )
    items = []
    for n in rows:
        item = _serialize(n)
        item["is_read"] = n.id in read_ids
        items.append(item)
    return ResponseModel(data={"items": items})


@router.get("/notifications/unread-count", response_model=ResponseModel)
def unread_count(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    all_ids = db.scalars(_mine_query(user).with_only_columns(Notification.id)).all()
    if not all_ids:
        return ResponseModel(data={"count": 0})
    read_ids = set(
        db.scalars(
            select(NotificationRead.notification_id).where(
                NotificationRead.user_id == user.id,
                NotificationRead.notification_id.in_(all_ids),
            )
        ).all()
    )
    return ResponseModel(data={"count": len(all_ids) - len(read_ids)})


@router.post("/notifications/{nid}/read", response_model=ResponseModel)
def mark_read(
    nid: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    n = db.get(Notification, nid)
    if not n:
        raise HTTPException(status_code=404, detail="消息不存在")
    exists = db.scalar(
        select(NotificationRead).where(
            NotificationRead.notification_id == nid,
            NotificationRead.user_id == user.id,
        )
    )
    if not exists:
        db.add(NotificationRead(notification_id=nid, user_id=user.id, read_at=datetime.now()))
        db.commit()
    return ResponseModel(message="已读")


@router.post("/notifications/read-all", response_model=ResponseModel)
def mark_all_read(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    all_ids = db.scalars(_mine_query(user).with_only_columns(Notification.id)).all()
    if not all_ids:
        return ResponseModel(message="无消息")
    read_ids = set(
        db.scalars(
            select(NotificationRead.notification_id).where(
                NotificationRead.user_id == user.id,
                NotificationRead.notification_id.in_(all_ids),
            )
        ).all()
    )
    now = datetime.now()
    for nid in all_ids:
        if nid not in read_ids:
            db.add(NotificationRead(notification_id=nid, user_id=user.id, read_at=now))
    db.commit()
    return ResponseModel(message="全部已读")
