from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import PointLog, User

INVITE_REWARD_INVITER = 50
INVITE_REWARD_INVITEE = 20


def ensure_invite_code(db: Session, user: User) -> str:
    if user.invite_code:
        return user.invite_code
    user.invite_code = f"ZXD{user.id:05d}"
    db.flush()
    return user.invite_code


def add_points(
    db: Session,
    user: User,
    points: int,
    log_type: str,
    remark: str,
    ref_order: str | None = None,
) -> PointLog:
    if points <= 0:
        raise ValueError("积分必须大于0")
    user.total_points += points
    log = PointLog(
        user_id=user.id,
        points=points,
        type=log_type,
        remark=remark,
        ref_order=ref_order,
    )
    db.add(log)
    return log


def adjust_points(
    db: Session,
    user: User,
    delta: int,
    remark: str,
) -> PointLog:
    if delta == 0:
        raise ValueError("调整积分不能为0")
    new_total = (user.total_points or 0) + delta
    if new_total < 0:
        raise ValueError("积分不足，无法扣减")
    user.total_points = new_total
    log = PointLog(
        user_id=user.id,
        points=delta,
        type="admin_adjust",
        remark=remark,
    )
    db.add(log)
    return log


def apply_invite_code(db: Session, user: User, invite_code: str) -> dict:
    code = invite_code.strip().upper()
    if not code:
        raise ValueError("请输入邀请码")
    ensure_invite_code(db, user)
    if user.invited_by:
        raise ValueError("您已使用过邀请码")
    if code == user.invite_code:
        raise ValueError("不能填写自己的邀请码")

    inviter = db.scalar(select(User).where(User.invite_code == code))
    if not inviter:
        raise ValueError("邀请码无效")

    user.invited_by = inviter.id
    add_points(db, user, INVITE_REWARD_INVITEE, "invite", f"填写邀请码-{code}")
    add_points(db, inviter, INVITE_REWARD_INVITER, "invite_reward", f"邀请好友-{user.nickname or user.id}")
    return {
        "inviter_nickname": inviter.nickname,
        "reward_points": INVITE_REWARD_INVITEE,
    }
