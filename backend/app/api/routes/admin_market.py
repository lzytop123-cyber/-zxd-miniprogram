"""上岸集市管理端接口。"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin
from app.db.session import get_db
from app.models import (
    AdminUser,
    MarketCategory,
    MarketListing,
    MarketListingStatus,
    MarketReport,
    MarketSensitiveWord,
    User,
)
from app.schemas.common import ResponseModel
from app.services import market_service as svc
from app.services.admin_audit import log_admin_action
from app.services.market_seed import ensure_market_categories

router = APIRouter(prefix="/admin/market", tags=["后台-上岸集市"])


class ReviewBody(BaseModel):
    approve: bool
    reject_reason: str | None = None


class ForceOffBody(BaseModel):
    violation: bool = False
    note: str | None = None


class ReportHandleBody(BaseModel):
    accept: bool
    handle_note: str | None = None
    take_down: bool = True


class BanBody(BaseModel):
    banned: bool
    reason: str | None = None
    ban_until: datetime | None = None


class CategoryBody(BaseModel):
    type: str
    code: str
    name: str
    sort_order: int = 0
    status: int = 1


class CategoryUpdateBody(BaseModel):
    name: str | None = None
    sort_order: int | None = None
    status: int | None = None


class SensitiveWordBody(BaseModel):
    word: str
    level: str = "block"
    status: int = 1


@router.get("/stats", response_model=ResponseModel)
def stats(_: AdminUser = Depends(get_current_admin), db: Session = Depends(get_db)):
    return ResponseModel(data=svc.market_stats(db))


@router.get("/categories", response_model=ResponseModel)
def list_categories(_: AdminUser = Depends(get_current_admin), db: Session = Depends(get_db)):
    ensure_market_categories(db)
    rows = db.scalars(
        select(MarketCategory).order_by(MarketCategory.type, MarketCategory.sort_order)
    ).all()
    return ResponseModel(
        data=[
            {
                "id": r.id,
                "type": r.type,
                "code": r.code,
                "name": r.name,
                "sort_order": r.sort_order,
                "status": r.status,
            }
            for r in rows
        ]
    )


@router.post("/categories", response_model=ResponseModel)
def create_category(
    body: CategoryBody,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    if body.type not in ("exam", "material"):
        raise HTTPException(status_code=400, detail="type 无效")
    row = MarketCategory(
        type=body.type,
        code=body.code.strip(),
        name=body.name.strip(),
        sort_order=body.sort_order,
        status=body.status,
    )
    db.add(row)
    log_admin_action(db, admin, "market_category_create", target_type="market_category", detail=body.code)
    db.commit()
    db.refresh(row)
    return ResponseModel(message="已创建", data={"id": row.id})


@router.put("/categories/{category_id}", response_model=ResponseModel)
def update_category(
    category_id: int,
    body: CategoryUpdateBody,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    row = db.get(MarketCategory, category_id)
    if not row:
        raise HTTPException(status_code=404, detail="分类不存在")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(row, k, v)
    log_admin_action(db, admin, "market_category_update", target_type="market_category", target_id=category_id)
    db.commit()
    return ResponseModel(message="已更新")


@router.get("/listings", response_model=ResponseModel)
def list_listings(
    status: str | None = None,
    q: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    rows, total = svc.query_listings(
        db,
        q=q,
        status=status,
        page=page,
        page_size=page_size,
    )
    return ResponseModel(
        data={
            "items": [svc.listing_to_dict(db, r, include_private=True) for r in rows],
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    )


@router.post("/listings/{listing_id}/review", response_model=ResponseModel)
def review_listing(
    listing_id: int,
    body: ReviewBody,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    listing = svc.admin_review_listing(
        db, admin, listing_id, approve=body.approve, reject_reason=body.reject_reason
    )
    log_admin_action(
        db,
        admin,
        "market_review",
        target_type="listing",
        target_id=listing_id,
        detail="approve" if body.approve else body.reject_reason,
    )
    db.commit()
    return ResponseModel(
        message="已通过" if body.approve else "已驳回",
        data=svc.listing_to_dict(db, listing, include_private=True),
    )


@router.post("/listings/{listing_id}/off", response_model=ResponseModel)
def force_off(
    listing_id: int,
    body: ForceOffBody,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    listing = svc.admin_force_off(
        db, admin, listing_id, violation=body.violation, note=body.note
    )
    log_admin_action(
        db,
        admin,
        "market_off",
        target_type="listing",
        target_id=listing_id,
        detail=body.note,
    )
    db.commit()
    return ResponseModel(message="已处理", data=svc.listing_to_dict(db, listing, include_private=True))


@router.get("/reports", response_model=ResponseModel)
def list_reports(
    status: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    from sqlalchemy import func

    q = select(MarketReport)
    if status:
        q = q.where(MarketReport.status == status)
    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    rows = db.scalars(
        q.order_by(MarketReport.id.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return ResponseModel(
        data={
            "items": [
                {
                    "id": r.id,
                    "listing_id": r.listing_id,
                    "reporter_id": r.reporter_id,
                    "reason_code": r.reason_code,
                    "detail": r.detail,
                    "status": r.status,
                    "handle_note": r.handle_note,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                    "handled_at": r.handled_at.isoformat() if r.handled_at else None,
                }
                for r in rows
            ],
            "total": int(total),
            "page": page,
            "page_size": page_size,
        }
    )


@router.post("/reports/{report_id}/handle", response_model=ResponseModel)
def handle_report(
    report_id: int,
    body: ReportHandleBody,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    row = svc.admin_handle_report(
        db,
        admin,
        report_id,
        accept=body.accept,
        handle_note=body.handle_note,
        take_down=body.take_down,
    )
    log_admin_action(
        db,
        admin,
        "market_report_handle",
        target_type="report",
        target_id=report_id,
        detail=body.handle_note,
    )
    db.commit()
    return ResponseModel(message="已处理", data={"id": row.id, "status": row.status})


@router.post("/users/{user_id}/ban", response_model=ResponseModel)
def ban_user(
    user_id: int,
    body: BanBody,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    user = svc.admin_set_user_ban(
        db,
        admin,
        user_id,
        banned=body.banned,
        reason=body.reason,
        until=body.ban_until,
    )
    log_admin_action(
        db,
        admin,
        "market_ban" if body.banned else "market_unban",
        target_type="user",
        target_id=user_id,
        detail=body.reason,
    )
    db.commit()
    return ResponseModel(
        message="已更新",
        data={
            "user_id": user.id,
            "market_banned": bool(user.market_banned),
            "market_ban_reason": user.market_ban_reason,
            "market_ban_until": user.market_ban_until.isoformat() if user.market_ban_until else None,
        },
    )


@router.get("/sensitive-words", response_model=ResponseModel)
def list_words(_: AdminUser = Depends(get_current_admin), db: Session = Depends(get_db)):
    rows = db.scalars(select(MarketSensitiveWord).order_by(MarketSensitiveWord.id.desc())).all()
    return ResponseModel(
        data=[
            {"id": r.id, "word": r.word, "level": r.level, "status": r.status}
            for r in rows
        ]
    )


@router.post("/sensitive-words", response_model=ResponseModel)
def add_word(
    body: SensitiveWordBody,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    word = body.word.strip()
    if not word:
        raise HTTPException(status_code=400, detail="词不能为空")
    if body.level not in ("block", "review"):
        raise HTTPException(status_code=400, detail="level 无效")
    exists = db.scalar(select(MarketSensitiveWord).where(MarketSensitiveWord.word == word))
    if exists:
        exists.level = body.level
        exists.status = body.status
        db.commit()
        return ResponseModel(message="已更新", data={"id": exists.id})
    row = MarketSensitiveWord(word=word, level=body.level, status=body.status)
    db.add(row)
    log_admin_action(db, admin, "market_sensitive_add", target_type="sensitive_word", detail=word)
    db.commit()
    db.refresh(row)
    return ResponseModel(message="已添加", data={"id": row.id})


@router.delete("/sensitive-words/{word_id}", response_model=ResponseModel)
def delete_word(
    word_id: int,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    row = db.get(MarketSensitiveWord, word_id)
    if not row:
        raise HTTPException(status_code=404, detail="不存在")
    db.delete(row)
    log_admin_action(db, admin, "market_sensitive_del", target_type="sensitive_word", target_id=word_id)
    db.commit()
    return ResponseModel(message="已删除")
