from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.security import create_access_token
from app.db.session import get_db
from app.models import PointLog, User, WechatSubscription
from app.schemas.common import ResponseModel
from app.schemas.user import (
    BindPhoneRequest,
    FaceUploadRequest,
    InviteApplyRequest,
    LoginRequest,
    LoginResponse,
    SubscribeRequest,
    UserProfile,
    UserProfileUpdate,
)
from app.services.business import WechatService
from app.services.points import apply_invite_code, ensure_invite_code

router = APIRouter(prefix="/user", tags=["用户"])


def _to_profile(db: Session, user: User) -> UserProfile:
    ensure_invite_code(db, user)
    return UserProfile(
        id=user.id,
        nickname=user.nickname,
        avatar_url=user.avatar_url,
        phone=user.phone,
        title=user.title,
        balance=user.balance,
        total_points=user.total_points,
        invite_code=user.invite_code,
        face_registered=bool(user.face_image),
    )


@router.post("/login", response_model=ResponseModel[LoginResponse])
async def login(body: LoginRequest, db: Session = Depends(get_db)):
    try:
        wx_data = await WechatService.code_to_openid(body.code)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    user = db.scalar(select(User).where(User.openid == wx_data["openid"]))
    if not user:
        user = User(openid=wx_data["openid"], nickname="知行岛学员", title="小白")
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
        user.nickname = body.nickname
    if body.avatar_url is not None:
        user.avatar_url = body.avatar_url
    db.commit()
    db.refresh(user)
    return ResponseModel(data=_to_profile(db, user))


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


@router.post("/subscribe", response_model=ResponseModel)
def save_subscriptions(
    body: SubscribeRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    for tmpl_id, status in body.subscriptions.items():
        sub = WechatSubscription(
            user_id=user.id,
            tmpl_id=tmpl_id,
            scene="booking",
            status=1 if status == "accept" else 0,
        )
        db.add(sub)
    db.commit()
    return ResponseModel(message="订阅状态已保存")
