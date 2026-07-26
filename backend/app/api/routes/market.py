"""上岸集市 C 端接口。"""

from __future__ import annotations

import uuid
from decimal import Decimal
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_optional_user
from app.core.config import settings
from app.core.static_url import public_static_path, public_static_url
from app.db.session import get_db
from app.models import MarketFavorite, MarketListing, MarketListingStatus, Store, User
from app.schemas.common import ResponseModel
from app.services import market_service as svc
from app.services.content_safety import check_listing_text, wechat_img_sec_check
from app.services.market_seed import ensure_market_categories

router = APIRouter(prefix="/market", tags=["上岸集市"])

UPLOAD_DIR = Path(__file__).resolve().parents[3] / "uploads" / "market"
IMAGE_TYPES = {
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/gif": "gif",
}


def _ensure_enabled() -> None:
    if not settings.feature_marketplace:
        raise svc.marketplace_disabled_error()


class ListingCreateBody(BaseModel):
    store_id: int
    exam_category_id: int
    material_category_id: int
    title: str
    description: str
    price: Decimal = Decimal("0")
    images: list[str] = Field(default_factory=list)
    copyright_declared: bool = False
    submit: bool = False


class ListingUpdateBody(BaseModel):
    store_id: int | None = None
    exam_category_id: int | None = None
    material_category_id: int | None = None
    title: str | None = None
    description: str | None = None
    price: Decimal | None = None
    images: list[str] | None = None
    copyright_declared: bool | None = None


class ContactCreateBody(BaseModel):
    listing_id: int
    message: str | None = None


class ContactDecideBody(BaseModel):
    approve: bool
    reveal_type: str | None = None
    wechat_id: str | None = None


class ReportCreateBody(BaseModel):
    listing_id: int
    reason_code: str
    detail: str | None = None
    images: list[str] = Field(default_factory=list)


class WechatIdBody(BaseModel):
    wechat_id: str


@router.get("/meta", response_model=ResponseModel)
def market_meta(db: Session = Depends(get_db), user: User | None = Depends(get_optional_user)):
    enabled = bool(settings.feature_marketplace)
    if not enabled:
        return ResponseModel(
            data={
                "enabled": False,
                "message": "功能暂未开放",
                "copyright_text": svc.copyright_text(),
            }
        )
    ensure_market_categories(db)
    exams = svc.list_active_categories(db, "exam")
    materials = svc.list_active_categories(db, "material")
    stores = db.scalars(select(Store).where(Store.status == 1).order_by(Store.id)).all()
    preferred = svc.preferred_store_id(db, user) if user else None
    return ResponseModel(
        data={
            "enabled": True,
            "copyright_text": svc.copyright_text(),
            "content_security_enabled": bool(settings.wx_content_security_enabled),
            "preferred_store_id": preferred,
            "exam_categories": [
                {"id": c.id, "code": c.code, "name": c.name} for c in exams
            ],
            "material_categories": [
                {"id": c.id, "code": c.code, "name": c.name} for c in materials
            ],
            "stores": [{"id": s.id, "name": s.name} for s in stores],
            "phone_bound": bool(user and user.phone),
            "market_banned": svc.is_market_banned(user) if user else False,
            "market_wechat_id": (user.market_wechat_id if user else None),
        }
    )


@router.get("/home", response_model=ResponseModel)
def market_home(
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
):
    _ensure_enabled()
    ensure_market_categories(db)
    latest, _ = svc.query_listings(db, page=1, page_size=10)
    recommended, _ = svc.query_listings(db, page=1, page_size=10)
    exams = svc.list_active_categories(db, "exam")
    materials = svc.list_active_categories(db, "material")
    return ResponseModel(
        data={
            "exam_categories": [{"id": c.id, "code": c.code, "name": c.name} for c in exams],
            "material_categories": [
                {"id": c.id, "code": c.code, "name": c.name} for c in materials
            ],
            "latest": [svc.listing_to_dict(db, r, viewer=user) for r in latest],
            "recommended": [svc.listing_to_dict(db, r, viewer=user) for r in recommended],
        }
    )


@router.get("/listings", response_model=ResponseModel)
def list_listings(
    q: str | None = None,
    store_id: int | None = None,
    exam_category_id: int | None = None,
    material_category_id: int | None = None,
    is_free: bool | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
):
    _ensure_enabled()
    rows, total = svc.query_listings(
        db,
        q=q,
        store_id=store_id,
        exam_category_id=exam_category_id,
        material_category_id=material_category_id,
        is_free=is_free,
        min_price=Decimal(str(min_price)) if min_price is not None else None,
        max_price=Decimal(str(max_price)) if max_price is not None else None,
        page=page,
        page_size=page_size,
    )
    return ResponseModel(
        data={
            "items": [svc.listing_to_dict(db, r, viewer=user) for r in rows],
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    )


@router.get("/listings/{listing_id}", response_model=ResponseModel)
def get_listing(
    listing_id: int,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
):
    _ensure_enabled()
    listing = svc.get_listing_for_viewer(db, listing_id, user)
    similar = svc.similar_listings(db, listing)
    return ResponseModel(
        data={
            "listing": svc.listing_to_dict(db, listing, viewer=user),
            "similar": [svc.listing_to_dict(db, r, viewer=user) for r in similar],
        }
    )


@router.post("/upload", response_model=ResponseModel)
async def upload_market_image(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
):
    _ensure_enabled()
    svc.require_phone(user)
    svc.require_not_market_banned(user)
    content_type = (file.content_type or "").lower()
    if content_type not in IMAGE_TYPES:
        raise HTTPException(status_code=400, detail="仅支持 jpg / png / webp / gif")
    content = await file.read()
    if len(content) > 2_000_000:
        raise HTTPException(status_code=400, detail="图片不能超过 2MB")
    safety = await wechat_img_sec_check(
        image_bytes=content,
        filename=file.filename or f"upload.{IMAGE_TYPES[content_type]}",
    )
    if not safety.ok:
        raise HTTPException(status_code=400, detail=safety.reason or "图片未通过安全检测")
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4().hex}.{IMAGE_TYPES[content_type]}"
    (UPLOAD_DIR / filename).write_bytes(content)
    path = f"/static/market/{filename}"
    return ResponseModel(
        data={"path": path, "url": public_static_url(path)}
    )


@router.post("/listings", response_model=ResponseModel)
async def create_listing(
    body: ListingCreateBody,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ensure_enabled()
    if body.submit:
        safety = await check_listing_text(
            db, openid=user.openid, title=body.title, description=body.description
        )
        if not safety.ok:
            raise HTTPException(status_code=400, detail=safety.reason or "内容未通过安全检测")
    listing = svc.create_listing(
        db,
        user,
        store_id=body.store_id,
        exam_category_id=body.exam_category_id,
        material_category_id=body.material_category_id,
        title=body.title,
        description=body.description,
        price=body.price,
        images=body.images,
        copyright_declared=body.copyright_declared,
        submit=body.submit,
    )
    return ResponseModel(message="已创建", data=svc.listing_to_dict(db, listing, viewer=user))


@router.put("/listings/{listing_id}", response_model=ResponseModel)
def update_listing(
    listing_id: int,
    body: ListingUpdateBody,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ensure_enabled()
    listing = svc.update_listing(
        db,
        user,
        listing_id,
        **body.model_dump(exclude_unset=True),
    )
    return ResponseModel(message="已更新", data=svc.listing_to_dict(db, listing, viewer=user))


@router.post("/listings/{listing_id}/submit", response_model=ResponseModel)
async def submit_listing(
    listing_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ensure_enabled()
    listing = db.get(MarketListing, listing_id)
    if not listing or listing.user_id != user.id:
        raise HTTPException(status_code=404, detail="资料不存在")
    safety = await check_listing_text(
        db, openid=user.openid, title=listing.title, description=listing.description
    )
    if not safety.ok:
        raise HTTPException(status_code=400, detail=safety.reason or "内容未通过安全检测")
    listing = svc.submit_listing(db, user, listing_id)
    return ResponseModel(message="已提交审核", data=svc.listing_to_dict(db, listing, viewer=user))


@router.post("/listings/{listing_id}/off", response_model=ResponseModel)
def off_listing(
    listing_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ensure_enabled()
    listing = svc.owner_set_status(db, user, listing_id, MarketListingStatus.off.value)
    return ResponseModel(message="已下架", data=svc.listing_to_dict(db, listing, viewer=user))


@router.post("/listings/{listing_id}/sold", response_model=ResponseModel)
def sold_listing(
    listing_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ensure_enabled()
    listing = svc.owner_set_status(db, user, listing_id, MarketListingStatus.sold.value)
    return ResponseModel(message="已标记已出", data=svc.listing_to_dict(db, listing, viewer=user))


@router.post("/favorites/{listing_id}", response_model=ResponseModel)
def add_favorite(
    listing_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ensure_enabled()
    return ResponseModel(data=svc.toggle_favorite(db, user, listing_id, True))


@router.delete("/favorites/{listing_id}", response_model=ResponseModel)
def remove_favorite(
    listing_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ensure_enabled()
    return ResponseModel(data=svc.toggle_favorite(db, user, listing_id, False))


@router.get("/mine/listings", response_model=ResponseModel)
def mine_listings(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ensure_enabled()
    rows, total = svc.query_listings(
        db, status=None, user_id=user.id, page=page, page_size=page_size
    )
    return ResponseModel(
        data={
            "items": [svc.listing_to_dict(db, r, viewer=user) for r in rows],
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    )


@router.get("/mine/favorites", response_model=ResponseModel)
def mine_favorites(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ensure_enabled()
    q = (
        select(MarketListing)
        .join(MarketFavorite, MarketFavorite.listing_id == MarketListing.id)
        .where(MarketFavorite.user_id == user.id)
        .order_by(MarketFavorite.id.desc())
    )
    from sqlalchemy import func

    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    rows = db.scalars(q.offset((page - 1) * page_size).limit(page_size)).all()
    return ResponseModel(
        data={
            "items": [svc.listing_to_dict(db, r, viewer=user) for r in rows],
            "total": int(total),
            "page": page,
            "page_size": page_size,
        }
    )


@router.post("/contact-requests", response_model=ResponseModel)
def create_contact(
    body: ContactCreateBody,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ensure_enabled()
    row = svc.create_contact_request(db, user, body.listing_id, body.message)
    return ResponseModel(message="已发起联系申请", data=svc.contact_to_dict(db, row, user))


@router.get("/contact-requests", response_model=ResponseModel)
def list_contacts(
    role: str = Query("all", pattern="^(all|buyer|seller)$"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ensure_enabled()
    from app.models import MarketContactRequest
    from sqlalchemy import or_

    q = select(MarketContactRequest)
    if role == "buyer":
        q = q.where(MarketContactRequest.buyer_id == user.id)
    elif role == "seller":
        q = q.where(MarketContactRequest.seller_id == user.id)
    else:
        q = q.where(
            or_(
                MarketContactRequest.buyer_id == user.id,
                MarketContactRequest.seller_id == user.id,
            )
        )
    rows = db.scalars(q.order_by(MarketContactRequest.id.desc()).limit(100)).all()
    return ResponseModel(
        data={"items": [svc.contact_to_dict(db, r, user) for r in rows]}
    )


@router.post("/contact-requests/{request_id}/decide", response_model=ResponseModel)
def decide_contact(
    request_id: int,
    body: ContactDecideBody,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ensure_enabled()
    row = svc.decide_contact_request(
        db,
        user,
        request_id,
        approve=body.approve,
        reveal_type=body.reveal_type,
        wechat_id=body.wechat_id,
    )
    return ResponseModel(
        message="已处理",
        data=svc.contact_to_dict(db, row, user, reveal=True),
    )


@router.get("/contact-requests/{request_id}/reveal", response_model=ResponseModel)
def reveal_contact(
    request_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ensure_enabled()
    from app.models import MarketContactRequest, MarketContactStatus

    row = db.get(MarketContactRequest, request_id)
    if not row or user.id not in (row.buyer_id, row.seller_id):
        raise HTTPException(status_code=404, detail="申请不存在")
    if row.status != MarketContactStatus.approved.value:
        raise HTTPException(status_code=403, detail="对方尚未同意或申请未通过")
    return ResponseModel(data=svc.contact_to_dict(db, row, user, reveal=True))


@router.post("/reports", response_model=ResponseModel)
def create_report(
    body: ReportCreateBody,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ensure_enabled()
    row = svc.create_report(
        db,
        user,
        listing_id=body.listing_id,
        reason_code=body.reason_code,
        detail=body.detail,
        images=body.images,
    )
    return ResponseModel(message="已提交举报", data={"id": row.id, "status": row.status})


@router.get("/mine/reports", response_model=ResponseModel)
def mine_reports(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ensure_enabled()
    from app.models import MarketReport

    rows = db.scalars(
        select(MarketReport)
        .where(MarketReport.reporter_id == user.id)
        .order_by(MarketReport.id.desc())
        .limit(50)
    ).all()
    return ResponseModel(
        data={
            "items": [
                {
                    "id": r.id,
                    "listing_id": r.listing_id,
                    "reason_code": r.reason_code,
                    "status": r.status,
                    "handle_note": r.handle_note,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                    "handled_at": r.handled_at.isoformat() if r.handled_at else None,
                }
                for r in rows
            ]
        }
    )


@router.put("/profile/wechat", response_model=ResponseModel)
def update_market_wechat(
    body: WechatIdBody,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ensure_enabled()
    svc.require_phone(user)
    wid = body.wechat_id.strip()
    if not wid or len(wid) > 64:
        raise HTTPException(status_code=400, detail="微信号无效")
    user.market_wechat_id = wid
    db.commit()
    return ResponseModel(message="已保存", data={"market_wechat_id": wid})
