from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.static_url import public_static_path, public_static_url
from app.core.security import create_access_token
from app.db.session import get_db
from app.models import PointLog, User, WechatSubscription
from app.schemas.common import ResponseModel
from app.schemas.user import (
    AvatarUploadRequest,
    BindPhoneRequest,
    FaceUploadRequest,
    InviteApplyRequest,
    LoginRequest,
    LoginResponse,
    STUDY_GOAL_LABELS,
    SubscribeRequest,
    UserProfile,
    UserProfileUpdate,
)
from app.services.business import WechatService
from app.services.points import apply_invite_code, ensure_invite_code

router = APIRouter(prefix="/user", tags=["用户"])

DEFAULT_NICKNAME = "知行岛学员"
AVATAR_DIR = Path(__file__).resolve().parents[3] / "uploads" / "avatars"


def _needs_profile_setup(user: User) -> bool:
    return not user.avatar_url or user.nickname in (None, "", DEFAULT_NICKNAME)


def _to_profile(db: Session, user: User) -> UserProfile:
    ensure_invite_code(db, user)
    goal = user.study_goal if user.study_goal in STUDY_GOAL_LABELS else None
    return UserProfile(
        id=user.id,
        nickname=user.nickname,
        avatar_url=public_static_path(user.avatar_url),
        phone=user.phone,
        title=user.title,
        study_goal=goal,
        study_goal_label=STUDY_GOAL_LABELS.get(goal) if goal else None,
        balance=user.balance,
        total_points=user.total_points,
        invite_code=user.invite_code,
        face_registered=bool(user.face_image),
        needs_profile_setup=_needs_profile_setup(user),
    )


@router.post("/login", response_model=ResponseModel[LoginResponse])
async def login(body: LoginRequest, db: Session = Depends(get_db)):
    try:
        wx_data = await WechatService.code_to_openid(body.code)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    user = db.scalar(select(User).where(User.openid == wx_data["openid"]))
    if not user:
        user = User(openid=wx_data["openid"], nickname=DEFAULT_NICKNAME, title="小白")
        db.add(user)
        db.flush()
        ensure_invite_code(db, user)
        db.commit()
        db.refresh(user)
    else:
        ensure_invite_code(db, user)
        db.commit()

    token = create_access_token(f"user:{user.id}")
    return ResponseModel(data=LoginResponse(token=token, user=_to_profile(db, user)))


@router.get("/profile", response_model=ResponseModel[UserProfile])
def get_profile(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return ResponseModel(data=_to_profile(db, user))


@router.put("/profile", response_model=ResponseModel[UserProfile])
def update_profile(
    body: UserProfileUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if body.nickname is not None:
        nickname = body.nickname.strip()
        if not nickname:
            raise HTTPException(status_code=400, detail="昵称不能为空")
        user.nickname = nickname[:32]
    if body.avatar_url is not None:
        user.avatar_url = body.avatar_url[:500]
    if body.study_goal is not None:
        goal = body.study_goal.strip() if body.study_goal else ""
        if goal and goal not in STUDY_GOAL_LABELS:
            raise HTTPException(status_code=400, detail="备考方向无效")
        user.study_goal = goal or None
    db.commit()
    db.refresh(user)
    return ResponseModel(data=_to_profile(db, user))


@router.post("/avatar", response_model=ResponseModel[UserProfile])
def upload_avatar(
    body: AvatarUploadRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """上传微信头像（chooseAvatar 临时文件转存）。"""
    import base64
    import re

    raw = body.avatar_image.strip()
    match = re.match(r"^data:image/(png|jpeg|jpg|webp);base64,(.+)$", raw, re.I)
    if match:
        ext = "jpg" if match.group(1).lower() in ("jpeg", "jpg") else match.group(1).lower()
        data = match.group(2)
    else:
        ext = "jpg"
        data = raw

    try:
        binary = base64.b64decode(data)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="头像数据无效") from exc

    if len(binary) > 200_000:
        raise HTTPException(status_code=400, detail="头像过大，请换一张")

    AVATAR_DIR.mkdir(parents=True, exist_ok=True)
    path = AVATAR_DIR / f"{user.id}.{ext}"
    path.write_bytes(binary)

    user.avatar_url = f"/static/avatars/{user.id}.{ext}"
    db.commit()
    db.refresh(user)
    return ResponseModel(message="头像已更新", data=_to_profile(db, user))


@router.post("/bind-phone", response_model=ResponseModel[UserProfile])
async def bind_phone(
    body: BindPhoneRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        phone = await WechatService.get_phone_number(body.code)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    user.phone = phone
    db.commit()
    db.refresh(user)
    return ResponseModel(data=_to_profile(db, user))


@router.post("/invite/apply", response_model=ResponseModel)
def apply_invite(
    body: InviteApplyRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        result = apply_invite_code(db, user, body.invite_code)
        db.commit()
        db.refresh(user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return ResponseModel(
        message=f"成功获得 {result['reward_points']} 积分",
        data=result,
    )


@router.get("/points/logs", response_model=ResponseModel)
def point_logs(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(
        select(PointLog)
        .where(PointLog.user_id == user.id)
        .order_by(PointLog.created_at.desc())
        .limit(50)
    ).all()
    return ResponseModel(
        data=[
            {
                "id": r.id,
                "points": r.points,
                "type": r.type,
                "remark": r.remark,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]
    )


@router.post("/face", response_model=ResponseModel[UserProfile])
def upload_face(
    body: FaceUploadRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """开发环境：保存人脸照片（生产对接门禁/人脸设备）。"""
    user.face_image = body.face_image[:500000]
    db.commit()
    db.refresh(user)
    return ResponseModel(message="人脸录入成功", data=_to_profile(db, user))


@router.get("/subscribe-config", response_model=ResponseModel)
def get_subscribe_config(user: User = Depends(get_current_user)):
    tmpl = (settings.wx_subscribe_card_expire_tmpl_id or "").strip()
    return ResponseModel(
        data={
            "card_expire_tmpl_id": tmpl or None,
            "enabled": bool(tmpl),
        }
    )


@router.post("/subscribe", response_model=ResponseModel)
def save_subscriptions(
    body: SubscribeRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.services.subscribe_notify import CARD_EXPIRE_SCENE

    tmpl_expire = (settings.wx_subscribe_card_expire_tmpl_id or "").strip()
    for tmpl_id, status in body.subscriptions.items():
        scene = CARD_EXPIRE_SCENE if tmpl_id == tmpl_expire else "booking"
        existing = db.scalar(
            select(WechatSubscription)
            .where(
                WechatSubscription.user_id == user.id,
                WechatSubscription.tmpl_id == tmpl_id,
            )
            .order_by(WechatSubscription.id.desc())
        )
        if existing:
            existing.status = 1 if status == "accept" else 0
            existing.scene = scene
        else:
            db.add(
                WechatSubscription(
                    user_id=user.id,
                    tmpl_id=tmpl_id,
                    scene=scene,
                    status=1 if status == "accept" else 0,
                )
            )
    db.commit()
    return ResponseModel(message="订阅状态已保存")
