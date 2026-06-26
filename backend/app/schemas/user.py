from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    code: str


class BindPhoneRequest(BaseModel):
    code: str


class UserProfileUpdate(BaseModel):
    nickname: str | None = None
    avatar_url: str | None = None


class UserProfile(BaseModel):
    id: int
    nickname: str | None = None
    avatar_url: str | None = None
    phone: str | None = None
    title: str | None = None
    balance: Decimal
    total_points: int
    invite_code: str | None = None
    face_registered: bool = False
    needs_profile_setup: bool = False

    model_config = {"from_attributes": True}


class AvatarUploadRequest(BaseModel):
    avatar_image: str = Field(min_length=10, max_length=300000)


class InviteApplyRequest(BaseModel):
    invite_code: str = Field(min_length=4, max_length=20)


class FaceUploadRequest(BaseModel):
    face_image: str = Field(min_length=10, max_length=500000)


class LoginResponse(BaseModel):
    token: str
    user: UserProfile


class SubscribeRequest(BaseModel):
    subscriptions: dict[str, str]
