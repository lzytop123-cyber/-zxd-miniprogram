"""上岸集市业务逻辑。"""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.static_url import public_static_path, public_static_url
from app.models import (
    AdminUser,
    MarketCategory,
    MarketCategoryType,
    MarketContactRequest,
    MarketContactStatus,
    MarketFavorite,
    MarketListing,
    MarketListingStatus,
    MarketModerationLog,
    MarketReport,
    MarketReportStatus,
    MarketRevealType,
    MarketSensitiveWord,
    Reservation,
    Store,
    User,
)
from app.services.market_seed import COPYRIGHT_TEXT_V1

EDITABLE_STATUSES = {
    MarketListingStatus.draft.value,
    MarketListingStatus.rejected.value,
    MarketListingStatus.off.value,
}
CONTACT_DAILY_LIMIT = 10


def marketplace_disabled_error() -> HTTPException:
    return HTTPException(status_code=403, detail="功能暂未开放")


def require_phone(user: User) -> None:
    if not (user.phone and str(user.phone).strip()):
        raise HTTPException(status_code=400, detail="请先绑定手机号")


def require_not_market_banned(user: User) -> None:
    if not user.market_banned:
        return
    until = user.market_ban_until
    if until and until < datetime.now():
        return
    raise HTTPException(status_code=403, detail="账号上岸集市功能已被限制")


def is_market_banned(user: User) -> bool:
    if not user.market_banned:
        return False
    until = user.market_ban_until
    if until and until < datetime.now():
        return False
    return True


def add_moderation_log(
    db: Session,
    *,
    target_type: str,
    target_id: str | int,
    action: str,
    admin_id: int | None = None,
    user_id: int | None = None,
    detail: str | None = None,
) -> None:
    db.add(
        MarketModerationLog(
            target_type=target_type,
            target_id=str(target_id),
            action=action,
            admin_id=admin_id,
            user_id=user_id,
            detail=detail,
        )
    )


def list_active_categories(db: Session, cat_type: str | None = None) -> list[MarketCategory]:
    q = select(MarketCategory).where(MarketCategory.status == 1)
    if cat_type:
        q = q.where(MarketCategory.type == cat_type)
    return list(db.scalars(q.order_by(MarketCategory.sort_order, MarketCategory.id)).all())


def get_category(db: Session, category_id: int, expect_type: str) -> MarketCategory:
    row = db.get(MarketCategory, category_id)
    if not row or row.status != 1 or row.type != expect_type:
        raise HTTPException(status_code=400, detail="分类无效")
    return row


def preferred_store_id(db: Session, user: User) -> int | None:
    if user.preferred_store_id:
        return user.preferred_store_id
    last = db.scalar(
        select(Reservation.store_id)
        .where(Reservation.user_id == user.id)
        .order_by(Reservation.id.desc())
        .limit(1)
    )
    return last


def _normalize_images(images: list[str] | None) -> list[str]:
    out: list[str] = []
    for item in images or []:
        path = public_static_path(str(item))
        if path.startswith("/static/market/"):
            out.append(path)
    return out[:9]


def listing_to_dict(
    db: Session,
    listing: MarketListing,
    *,
    viewer: User | None = None,
    include_private: bool = False,
) -> dict:
    seller = db.get(User, listing.user_id)
    store = db.get(Store, listing.store_id)
    exam = db.get(MarketCategory, listing.exam_category_id)
    material = db.get(MarketCategory, listing.material_category_id)
    favorited = False
    if viewer:
        favorited = (
            db.scalar(
                select(MarketFavorite.id).where(
                    MarketFavorite.user_id == viewer.id,
                    MarketFavorite.listing_id == listing.id,
                )
            )
            is not None
        )
    raw_images = listing.images or []
    # 管理端需要可直接打开的完整 URL；小程序端用相对 /static 路径再拼域名
    if include_private:
        images = [public_static_url(i) or public_static_path(i) for i in raw_images]
    else:
        images = [public_static_path(i) for i in raw_images]
    data = {
        "id": listing.id,
        "title": listing.title,
        "description": listing.description,
        "price": float(listing.price or 0),
        "is_free": bool(listing.is_free),
        "images": images,
        "cover": images[0] if images else None,
        "status": listing.status,
        "store_id": listing.store_id,
        "store_name": store.name if store else None,
        "exam_category_id": listing.exam_category_id,
        "exam_category_name": exam.name if exam else None,
        "material_category_id": listing.material_category_id,
        "material_category_name": material.name if material else None,
        "view_count": listing.view_count or 0,
        "favorite_count": listing.favorite_count or 0,
        "contact_count": listing.contact_count or 0,
        "published_at": listing.published_at.isoformat() if listing.published_at else None,
        "created_at": listing.created_at.isoformat() if listing.created_at else None,
        "updated_at": listing.updated_at.isoformat() if listing.updated_at else None,
        "favorited": favorited,
        "seller": {
            "id": seller.id if seller else None,
            "nickname": seller.nickname if seller else None,
            "avatar_url": public_static_path(seller.avatar_url) if seller else None,
            "title": seller.title if seller else None,
            "violation_count": (seller.market_violation_count or 0) if seller else 0,
            "banned": is_market_banned(seller) if seller else False,
        },
        "is_owner": bool(viewer and viewer.id == listing.user_id),
        "my_contact": None,
    }
    if include_private or (viewer and viewer.id == listing.user_id):
        data["reject_reason"] = listing.reject_reason
        data["copyright_declared"] = bool(listing.copyright_declared)
    if viewer and viewer.id != listing.user_id:
        data["my_contact"] = _viewer_contact_summary(db, listing.id, viewer.id)
    return data


def _viewer_contact_summary(
    db: Session, listing_id: int, buyer_id: int
) -> dict | None:
    rows = list(
        db.scalars(
            select(MarketContactRequest)
            .where(
                MarketContactRequest.listing_id == listing_id,
                MarketContactRequest.buyer_id == buyer_id,
            )
            .order_by(MarketContactRequest.id.desc())
        ).all()
    )
    if not rows:
        return None
    chosen = next(
        (r for r in rows if r.status == MarketContactStatus.approved.value),
        None,
    )
    if not chosen:
        chosen = next(
            (r for r in rows if r.status == MarketContactStatus.pending.value),
            rows[0],
        )
    data = {"id": chosen.id, "status": chosen.status}
    if chosen.status == MarketContactStatus.approved.value:
        data["reveal_type"] = chosen.reveal_type
        data["reveal_value"] = chosen.reveal_value
    return data


def create_listing(
    db: Session,
    user: User,
    *,
    store_id: int,
    exam_category_id: int,
    material_category_id: int,
    title: str,
    description: str,
    price: Decimal,
    images: list[str] | None,
    copyright_declared: bool,
    submit: bool,
) -> MarketListing:
    require_phone(user)
    require_not_market_banned(user)
    store = db.get(Store, store_id)
    if not store or store.status != 1:
        raise HTTPException(status_code=400, detail="门店无效")
    get_category(db, exam_category_id, MarketCategoryType.exam.value)
    get_category(db, material_category_id, MarketCategoryType.material.value)
    title = title.strip()
    description = description.strip()
    if not title or len(title) > 100:
        raise HTTPException(status_code=400, detail="标题无效")
    if not description or len(description) > 5000:
        raise HTTPException(status_code=400, detail="介绍无效")
    if price < 0:
        raise HTTPException(status_code=400, detail="价格无效")
    if submit and not copyright_declared:
        raise HTTPException(status_code=400, detail="请勾选原创或版权声明")
    imgs = _normalize_images(images)
    if submit and not imgs:
        raise HTTPException(status_code=400, detail="请至少上传一张图片")

    listing = MarketListing(
        user_id=user.id,
        store_id=store_id,
        exam_category_id=exam_category_id,
        material_category_id=material_category_id,
        title=title,
        description=description,
        price=price,
        is_free=1 if price == 0 else 0,
        images=imgs,
        copyright_declared=1 if copyright_declared else 0,
        copyright_text_version="v1" if copyright_declared else None,
        status=MarketListingStatus.draft.value,
    )
    db.add(listing)
    db.flush()
    if submit:
        listing.status = MarketListingStatus.pending.value
        add_moderation_log(
            db,
            target_type="listing",
            target_id=listing.id,
            action="submit",
            user_id=user.id,
        )
    user.preferred_store_id = store_id
    db.commit()
    db.refresh(listing)
    return listing


def update_listing(
    db: Session,
    user: User,
    listing_id: int,
    *,
    store_id: int | None = None,
    exam_category_id: int | None = None,
    material_category_id: int | None = None,
    title: str | None = None,
    description: str | None = None,
    price: Decimal | None = None,
    images: list[str] | None = None,
    copyright_declared: bool | None = None,
) -> MarketListing:
    require_phone(user)
    require_not_market_banned(user)
    listing = db.get(MarketListing, listing_id)
    if not listing or listing.user_id != user.id:
        raise HTTPException(status_code=404, detail="资料不存在")
    if listing.status == MarketListingStatus.published.value:
        raise HTTPException(status_code=400, detail="请先下架后再编辑")
    if listing.status not in EDITABLE_STATUSES and listing.status != MarketListingStatus.pending.value:
        raise HTTPException(status_code=400, detail="当前状态不可编辑")
    if listing.status == MarketListingStatus.pending.value:
        raise HTTPException(status_code=400, detail="审核中不可编辑，请等待结果")

    if store_id is not None:
        store = db.get(Store, store_id)
        if not store or store.status != 1:
            raise HTTPException(status_code=400, detail="门店无效")
        listing.store_id = store_id
    if exam_category_id is not None:
        get_category(db, exam_category_id, MarketCategoryType.exam.value)
        listing.exam_category_id = exam_category_id
    if material_category_id is not None:
        get_category(db, material_category_id, MarketCategoryType.material.value)
        listing.material_category_id = material_category_id
    if title is not None:
        title = title.strip()
        if not title or len(title) > 100:
            raise HTTPException(status_code=400, detail="标题无效")
        listing.title = title
    if description is not None:
        description = description.strip()
        if not description or len(description) > 5000:
            raise HTTPException(status_code=400, detail="介绍无效")
        listing.description = description
    if price is not None:
        if price < 0:
            raise HTTPException(status_code=400, detail="价格无效")
        listing.price = price
        listing.is_free = 1 if price == 0 else 0
    if images is not None:
        listing.images = _normalize_images(images)
    if copyright_declared is not None:
        listing.copyright_declared = 1 if copyright_declared else 0
        listing.copyright_text_version = "v1" if copyright_declared else None

    db.commit()
    db.refresh(listing)
    return listing


def submit_listing(db: Session, user: User, listing_id: int) -> MarketListing:
    require_phone(user)
    require_not_market_banned(user)
    listing = db.get(MarketListing, listing_id)
    if not listing or listing.user_id != user.id:
        raise HTTPException(status_code=404, detail="资料不存在")
    if listing.status not in {
        MarketListingStatus.draft.value,
        MarketListingStatus.rejected.value,
        MarketListingStatus.off.value,
    }:
        raise HTTPException(status_code=400, detail="当前状态不可提交审核")
    if not listing.copyright_declared:
        raise HTTPException(status_code=400, detail="请勾选原创或版权声明")
    if not listing.images:
        raise HTTPException(status_code=400, detail="请至少上传一张图片")
    listing.status = MarketListingStatus.pending.value
    listing.reject_reason = None
    add_moderation_log(
        db, target_type="listing", target_id=listing.id, action="submit", user_id=user.id
    )
    db.commit()
    db.refresh(listing)
    return listing


def owner_set_status(
    db: Session, user: User, listing_id: int, status: str
) -> MarketListing:
    require_phone(user)
    listing = db.get(MarketListing, listing_id)
    if not listing or listing.user_id != user.id:
        raise HTTPException(status_code=404, detail="资料不存在")
    if status == MarketListingStatus.off.value:
        if listing.status not in {
            MarketListingStatus.published.value,
            MarketListingStatus.sold.value,
        }:
            raise HTTPException(status_code=400, detail="当前状态不可下架")
    elif status == MarketListingStatus.sold.value:
        if listing.status not in {
            MarketListingStatus.published.value,
            MarketListingStatus.off.value,
        }:
            raise HTTPException(status_code=400, detail="当前状态不可标记已出")
    else:
        raise HTTPException(status_code=400, detail="不支持的状态")
    listing.status = status
    add_moderation_log(
        db,
        target_type="listing",
        target_id=listing.id,
        action=status,
        user_id=user.id,
    )
    db.commit()
    db.refresh(listing)
    return listing


def query_listings(
    db: Session,
    *,
    q: str | None = None,
    store_id: int | None = None,
    exam_category_id: int | None = None,
    material_category_id: int | None = None,
    is_free: bool | None = None,
    min_price: Decimal | None = None,
    max_price: Decimal | None = None,
    status: str | None = MarketListingStatus.published.value,
    user_id: int | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[MarketListing], int]:
    query = select(MarketListing)
    if status is not None:
        query = query.where(MarketListing.status == status)
    if user_id:
        query = query.where(MarketListing.user_id == user_id)
    if store_id:
        query = query.where(MarketListing.store_id == store_id)
    if exam_category_id:
        query = query.where(MarketListing.exam_category_id == exam_category_id)
    if material_category_id:
        query = query.where(MarketListing.material_category_id == material_category_id)
    if is_free is True:
        query = query.where(MarketListing.is_free == 1)
    elif is_free is False:
        query = query.where(MarketListing.is_free == 0)
    if min_price is not None:
        query = query.where(MarketListing.price >= min_price)
    if max_price is not None:
        query = query.where(MarketListing.price <= max_price)
    if q:
        like = f"%{q.strip()}%"
        query = query.where(
            or_(MarketListing.title.like(like), MarketListing.description.like(like))
        )

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.scalars(
        query.order_by(MarketListing.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return list(rows), int(total)


def get_listing_for_viewer(
    db: Session, listing_id: int, viewer: User | None
) -> MarketListing:
    listing = db.get(MarketListing, listing_id)
    if not listing:
        raise HTTPException(status_code=404, detail="资料不存在")
    is_owner = viewer and viewer.id == listing.user_id
    if listing.status != MarketListingStatus.published.value and not is_owner:
        raise HTTPException(status_code=404, detail="资料不存在或未公开")
    if listing.status == MarketListingStatus.published.value:
        listing.view_count = (listing.view_count or 0) + 1
        db.commit()
        db.refresh(listing)
    return listing


def toggle_favorite(db: Session, user: User, listing_id: int, add: bool) -> dict:
    listing = db.get(MarketListing, listing_id)
    if not listing or listing.status != MarketListingStatus.published.value:
        raise HTTPException(status_code=404, detail="资料不存在")
    row = db.scalar(
        select(MarketFavorite).where(
            MarketFavorite.user_id == user.id,
            MarketFavorite.listing_id == listing_id,
        )
    )
    if add:
        if not row:
            db.add(MarketFavorite(user_id=user.id, listing_id=listing_id))
            listing.favorite_count = (listing.favorite_count or 0) + 1
    else:
        if row:
            db.delete(row)
            listing.favorite_count = max(0, (listing.favorite_count or 0) - 1)
    db.commit()
    return {"favorited": add, "favorite_count": listing.favorite_count or 0}


def create_contact_request(
    db: Session, buyer: User, listing_id: int, message: str | None
) -> MarketContactRequest:
    require_phone(buyer)
    require_not_market_banned(buyer)
    listing = db.get(MarketListing, listing_id)
    if not listing or listing.status != MarketListingStatus.published.value:
        raise HTTPException(status_code=404, detail="资料不存在")
    if listing.user_id == buyer.id:
        raise HTTPException(status_code=400, detail="不能联系自己的发布")
    seller = db.get(User, listing.user_id)
    if not seller or is_market_banned(seller):
        raise HTTPException(status_code=400, detail="卖家暂不可联系")

    since = datetime.now() - timedelta(days=1)
    daily = db.scalar(
        select(func.count())
        .select_from(MarketContactRequest)
        .where(
            MarketContactRequest.buyer_id == buyer.id,
            MarketContactRequest.created_at >= since,
        )
    ) or 0
    if daily >= CONTACT_DAILY_LIMIT:
        raise HTTPException(status_code=400, detail="今日联系申请已达上限")

    existing = list(
        db.scalars(
            select(MarketContactRequest).where(
                MarketContactRequest.listing_id == listing_id,
                MarketContactRequest.buyer_id == buyer.id,
                MarketContactRequest.status.in_(
                    [
                        MarketContactStatus.pending.value,
                        MarketContactStatus.approved.value,
                    ]
                ),
            )
        ).all()
    )
    if any(r.status == MarketContactStatus.approved.value for r in existing):
        raise HTTPException(status_code=400, detail="对方已同意，请在详情页查看联系方式")
    if any(r.status == MarketContactStatus.pending.value for r in existing):
        raise HTTPException(status_code=400, detail="已有待处理的联系申请")

    row = MarketContactRequest(
        listing_id=listing_id,
        buyer_id=buyer.id,
        seller_id=listing.user_id,
        message=(message or "").strip()[:200] or None,
        status=MarketContactStatus.pending.value,
        expired_at=datetime.now() + timedelta(days=7),
    )
    db.add(row)
    listing.contact_count = (listing.contact_count or 0) + 1
    db.commit()
    db.refresh(row)
    return row


def decide_contact_request(
    db: Session,
    seller: User,
    request_id: int,
    *,
    approve: bool,
    reveal_type: str | None = None,
    wechat_id: str | None = None,
) -> MarketContactRequest:
    require_phone(seller)
    require_not_market_banned(seller)
    row = db.get(MarketContactRequest, request_id)
    if not row or row.seller_id != seller.id:
        raise HTTPException(status_code=404, detail="申请不存在")
    if row.status != MarketContactStatus.pending.value:
        raise HTTPException(status_code=400, detail="申请已处理")
    if row.expired_at and row.expired_at < datetime.now():
        row.status = MarketContactStatus.expired.value
        db.commit()
        raise HTTPException(status_code=400, detail="申请已过期")

    if not approve:
        row.status = MarketContactStatus.rejected.value
        row.decided_at = datetime.now()
        db.commit()
        db.refresh(row)
        return row

    if reveal_type not in {
        MarketRevealType.wechat.value,
        MarketRevealType.phone.value,
    }:
        raise HTTPException(status_code=400, detail="请选择展示微信号或手机号")
    if reveal_type == MarketRevealType.phone.value:
        if not seller.phone:
            raise HTTPException(status_code=400, detail="请先绑定手机号")
        reveal_value = seller.phone
    else:
        wid = (wechat_id or seller.market_wechat_id or "").strip()
        if not wid:
            raise HTTPException(status_code=400, detail="请填写微信号")
        seller.market_wechat_id = wid[:64]
        reveal_value = wid

    row.status = MarketContactStatus.approved.value
    row.reveal_type = reveal_type
    row.reveal_value = reveal_value
    row.decided_at = datetime.now()
    db.commit()
    db.refresh(row)
    return row


def contact_to_dict(
    db: Session, row: MarketContactRequest, viewer: User, *, reveal: bool = False
) -> dict:
    listing = db.get(MarketListing, row.listing_id)
    data = {
        "id": row.id,
        "listing_id": row.listing_id,
        "listing_title": listing.title if listing else None,
        "buyer_id": row.buyer_id,
        "seller_id": row.seller_id,
        "message": row.message,
        "status": row.status,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "decided_at": row.decided_at.isoformat() if row.decided_at else None,
        "role": "seller" if viewer.id == row.seller_id else "buyer",
    }
    if (
        reveal
        and row.status == MarketContactStatus.approved.value
        and viewer.id in (row.buyer_id, row.seller_id)
    ):
        data["reveal_type"] = row.reveal_type
        data["reveal_value"] = row.reveal_value
    return data


def create_report(
    db: Session,
    user: User,
    *,
    listing_id: int,
    reason_code: str,
    detail: str | None,
    images: list[str] | None,
) -> MarketReport:
    listing = db.get(MarketListing, listing_id)
    if not listing:
        raise HTTPException(status_code=404, detail="资料不存在")
    reason = (reason_code or "").strip()
    if not reason:
        raise HTTPException(status_code=400, detail="请选择举报原因")
    row = MarketReport(
        listing_id=listing_id,
        reporter_id=user.id,
        reason_code=reason[:40],
        detail=(detail or "").strip()[:500] or None,
        images=_normalize_images(images),
        status=MarketReportStatus.pending.value,
    )
    db.add(row)
    add_moderation_log(
        db,
        target_type="report",
        target_id="pending",
        action="create",
        user_id=user.id,
        detail=f"listing={listing_id}",
    )
    db.commit()
    db.refresh(row)
    add_moderation_log(
        db,
        target_type="report",
        target_id=row.id,
        action="created",
        user_id=user.id,
    )
    db.commit()
    return row


def admin_review_listing(
    db: Session,
    admin: AdminUser,
    listing_id: int,
    *,
    approve: bool,
    reject_reason: str | None = None,
) -> MarketListing:
    listing = db.get(MarketListing, listing_id)
    if not listing:
        raise HTTPException(status_code=404, detail="资料不存在")
    if listing.status != MarketListingStatus.pending.value:
        raise HTTPException(status_code=400, detail="仅待审核可处理")
    listing.reviewed_at = datetime.now()
    listing.reviewed_by = admin.id
    if approve:
        listing.status = MarketListingStatus.published.value
        listing.published_at = datetime.now()
        listing.reject_reason = None
        action = "approve"
    else:
        reason = (reject_reason or "").strip()
        if not reason:
            raise HTTPException(status_code=400, detail="请填写驳回原因")
        listing.status = MarketListingStatus.rejected.value
        listing.reject_reason = reason[:200]
        action = "reject"
    add_moderation_log(
        db,
        target_type="listing",
        target_id=listing.id,
        action=action,
        admin_id=admin.id,
        detail=reject_reason,
    )
    db.commit()
    db.refresh(listing)
    return listing


def admin_force_off(
    db: Session,
    admin: AdminUser,
    listing_id: int,
    *,
    violation: bool,
    note: str | None,
) -> MarketListing:
    listing = db.get(MarketListing, listing_id)
    if not listing:
        raise HTTPException(status_code=404, detail="资料不存在")
    listing.status = (
        MarketListingStatus.violation.value if violation else MarketListingStatus.off.value
    )
    listing.reviewed_at = datetime.now()
    listing.reviewed_by = admin.id
    if violation:
        seller = db.get(User, listing.user_id)
        if seller:
            seller.market_violation_count = (seller.market_violation_count or 0) + 1
    add_moderation_log(
        db,
        target_type="listing",
        target_id=listing.id,
        action="violation" if violation else "admin_off",
        admin_id=admin.id,
        detail=note,
    )
    db.commit()
    db.refresh(listing)
    return listing


def admin_handle_report(
    db: Session,
    admin: AdminUser,
    report_id: int,
    *,
    accept: bool,
    handle_note: str | None,
    take_down: bool = True,
) -> MarketReport:
    row = db.get(MarketReport, report_id)
    if not row:
        raise HTTPException(status_code=404, detail="举报不存在")
    if row.status != MarketReportStatus.pending.value:
        raise HTTPException(status_code=400, detail="已处理")
    row.handler_admin_id = admin.id
    row.handled_at = datetime.now()
    row.handle_note = (handle_note or "").strip()[:200] or None
    if accept:
        row.status = MarketReportStatus.accepted.value
        if take_down:
            admin_force_off(db, admin, row.listing_id, violation=True, note="举报成立")
    else:
        row.status = MarketReportStatus.rejected.value
    add_moderation_log(
        db,
        target_type="report",
        target_id=row.id,
        action="accept" if accept else "reject_report",
        admin_id=admin.id,
        detail=handle_note,
    )
    db.commit()
    db.refresh(row)
    return row


def admin_set_user_ban(
    db: Session,
    admin: AdminUser,
    user_id: int,
    *,
    banned: bool,
    reason: str | None,
    until: datetime | None,
) -> User:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    user.market_banned = 1 if banned else 0
    user.market_ban_reason = (reason or "").strip()[:200] if banned else None
    user.market_ban_until = until if banned else None
    add_moderation_log(
        db,
        target_type="user",
        target_id=user.id,
        action="ban" if banned else "unban",
        admin_id=admin.id,
        detail=reason,
    )
    db.commit()
    db.refresh(user)
    return user


def similar_listings(db: Session, listing: MarketListing, limit: int = 6) -> list[MarketListing]:
    rows = db.scalars(
        select(MarketListing)
        .where(
            MarketListing.status == MarketListingStatus.published.value,
            MarketListing.id != listing.id,
            or_(
                MarketListing.exam_category_id == listing.exam_category_id,
                MarketListing.material_category_id == listing.material_category_id,
            ),
        )
        .order_by(MarketListing.id.desc())
        .limit(limit)
    ).all()
    return list(rows)


def market_stats(db: Session) -> dict:
    published = db.scalar(
        select(func.count()).where(MarketListing.status == MarketListingStatus.published.value)
    ) or 0
    pending = db.scalar(
        select(func.count()).where(MarketListing.status == MarketListingStatus.pending.value)
    ) or 0
    favorites = db.scalar(select(func.count()).select_from(MarketFavorite)) or 0
    contacts = db.scalar(select(func.count()).select_from(MarketContactRequest)) or 0
    views = db.scalar(select(func.coalesce(func.sum(MarketListing.view_count), 0))) or 0
    return {
        "published": int(published),
        "pending": int(pending),
        "favorites": int(favorites),
        "contacts": int(contacts),
        "views": int(views),
    }


def copyright_text() -> str:
    return COPYRIGHT_TEXT_V1
