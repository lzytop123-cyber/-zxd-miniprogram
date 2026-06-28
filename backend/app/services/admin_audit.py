"""后台操作审计日志。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import AdminOperationLog, AdminUser


def log_admin_action(
    db: Session,
    admin: AdminUser,
    action: str,
    *,
    target_type: str | None = None,
    target_id: str | int | None = None,
    detail: str | None = None,
) -> AdminOperationLog:
    row = AdminOperationLog(
        admin_id=admin.id,
        admin_username=admin.username,
        action=action,
        target_type=target_type,
        target_id=str(target_id) if target_id is not None else None,
        detail=detail,
    )
    db.add(row)
    return row
