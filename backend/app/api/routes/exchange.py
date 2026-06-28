from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import (
    CardSource,
    MeituanDealMapping,
    MeituanOrder,
    MeituanOrderStatus,
    User,
)
from app.schemas.common import ResponseModel
from app.services.card_service import get_mapping_by_deal_id, issue_period_card
from app.services.deal_mapping_service import (
    guess_reward_from_name,
    mark_pending_resolved_by_deal_id,
    record_pending_deal,
)
from app.services.yunlaoban import YunlaobanService

router = APIRouter(prefix="/exchange", tags=["兑换"])


class ExchangeRequest(BaseModel):
    code: str = Field(min_length=6, max_length=32)
    store_id: int | None = None


@router.post("/meituan/{code}", response_model=ResponseModel)
async def exchange_meituan(
    code: str = Path(..., min_length=6, max_length=32, description="团购券码"),
    store_id: int | None = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return await _exchange(
        ExchangeRequest(code=code, store_id=store_id), user, db, platform=1, source=CardSource.meituan
    )


@router.post("/douyin/{code}", response_model=ResponseModel)
async def exchange_douyin(
    code: str = Path(..., min_length=6, max_length=32, description="团购券码"),
    store_id: int | None = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return await _exchange(
        ExchangeRequest(code=code, store_id=store_id), user, db, platform=2, source=CardSource.douyin
    )


async def _exchange(
    body: ExchangeRequest,
    user: User,
    db: Session,
    platform: int,
    source: CardSource,
):
    code = body.code.strip()
    existing = db.scalar(select(MeituanOrder).where(MeituanOrder.coupon_code == code))
    if existing and existing.status == MeituanOrderStatus.verified:
        raise HTTPException(status_code=400, detail="该券码已兑换")

    try:
        prepared = await YunlaobanService.prepare(platform, code)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    deal_id = str(prepared["ticketData"].get("dealId", ""))
    mapping = get_mapping_by_deal_id(db, deal_id)
    if not mapping:
        ticket_name = prepared.get("ticketName") or prepared["ticketData"].get("dealTitle", "")
        # 自动识别并创建映射，无需管理员手动配置
        reward_type, reward_value = guess_reward_from_name(ticket_name)
        mapping = MeituanDealMapping(
            store_id=body.store_id,
            deal_id=deal_id,
            deal_name=ticket_name,
            reward_type=reward_type,
            reward_value=reward_value,
            platform=platform,
            is_active=1,
        )
        db.add(mapping)
        # 同时记录到待配置列表，方便管理员后续查看/调整
        record_pending_deal(
            db,
            deal_id=deal_id,
            deal_name=ticket_name,
            platform=platform,
            coupon_code=code,
            ticket_data=prepared.get("ticketData"),
        )
        mark_pending_resolved_by_deal_id(db, deal_id)
        db.commit()
        db.refresh(mapping)

    try:
        consume_result = await YunlaobanService.consume(platform, code, prepared["ticketInfo"])
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    card = issue_period_card(
        db,
        user.id,
        mapping,
        source=source,
        receipt=code,
        store_id=body.store_id,
    )

    order = MeituanOrder(
        meituan_deal_id=deal_id,
        user_id=user.id,
        coupon_code=code,
        deal_name=prepared.get("ticketName") or mapping.deal_name,
        deal_type=mapping.reward_type.value,
        store_id=body.store_id or mapping.store_id,
        status=MeituanOrderStatus.verified,
        verified_at=datetime.now(),
        meituan_raw={"result": consume_result, "ticketData": prepared["ticketData"]},
    )
    db.add(order)
    db.commit()
    db.refresh(card)

    return ResponseModel(
        message=f"已成功兑换 {mapping.deal_name}",
        data={
            "card_id": card.id,
            "card_name": card.card_name,
            "card_type": card.card_type.value,
            "end_date": str(card.end_date) if card.end_date else None,
            "remaining_hours": float(card.remaining_hours) if card.remaining_hours else None,
            "total_hours": float(card.total_hours) if card.total_hours else None,
            "remaining_sessions": card.remaining_sessions,
        },
    )


@router.get("/records", response_model=ResponseModel)
def exchange_records(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(
        select(MeituanOrder)
        .where(MeituanOrder.user_id == user.id)
        .order_by(MeituanOrder.created_at.desc())
        .limit(30)
    ).all()
    return ResponseModel(
        data=[
            {
                "id": r.id,
                "deal_name": r.deal_name,
                "coupon_code": r.coupon_code,
                "status": r.status.value,
                "verified_at": r.verified_at.isoformat() if r.verified_at else None,
            }
            for r in rows
        ]
    )
