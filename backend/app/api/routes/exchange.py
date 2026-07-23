import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import (
    CardSource,
    MeituanDealMapping,
    MeituanOrder,
    MeituanOrderStatus,
    PeriodCard,
    User,
)
from app.schemas.common import ResponseModel
from app.services.card_service import card_validity_api_fields, get_mapping_by_deal_id, issue_period_card
from app.services.deal_mapping_service import (
    guess_limit_per_user_from_name,
    guess_reward_from_name,
    mapping_limit_per_user,
    mark_pending_resolved_by_deal_id,
    record_pending_deal,
    user_redeemed_deal_count,
)
from app.services.douyin import DouyinService, parse_douyin_voucher_expire_date, use_douyin_official
from app.services.yunlaoban import YunlaobanService, parse_voucher_expire_date

router = APIRouter(prefix="/exchange", tags=["兑换"])


async def _prepare(platform: int, code: str) -> tuple[dict, dict | None]:
    """验券准备（不核销）。返回 (yunlaoban 形态 prepared, 抖音原始 prepared 或 None)。"""
    if platform == 2 and use_douyin_official():
        import httpx
        from app.core.config import settings

        timeout = settings.yunlaoban_timeout_sec
        async with httpx.AsyncClient(timeout=timeout) as client:
            raw = await DouyinService._prepare_with_client(client, code)
        shape = {
            "ticketInfo": raw.get("verify_token") or "",
            "ticketName": raw.get("ticketName") or "",
            "ticketData": raw.get("ticketData") or {},
        }
        return shape, raw
    prepared = await YunlaobanService.prepare(platform, code)
    return prepared, None


async def _consume(platform: int, code: str, prepared: dict, douyin_raw: dict | None) -> str:
    """正式核销。"""
    if platform == 2 and use_douyin_official():
        import httpx
        from app.core.config import settings

        if not douyin_raw:
            raise ValueError("抖音验券状态丢失，请重试")
        timeout = settings.yunlaoban_timeout_sec
        async with httpx.AsyncClient(timeout=timeout) as client:
            verified = await DouyinService._verify_with_client(client, douyin_raw)
        return json.dumps(verified, ensure_ascii=False)
    return await YunlaobanService.consume(platform, code, prepared["ticketInfo"])


def _parse_voucher_expire(ticket_data: dict | None, platform: int):
    if platform == 2 and use_douyin_official():
        return parse_douyin_voucher_expire_date(ticket_data)
    return parse_voucher_expire_date(ticket_data)


class ExchangeRequest(BaseModel):
    code: str = Field(min_length=6, max_length=2048)
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
    code: str = Path(..., min_length=6, max_length=2048, description="团购券码或抖音扫码链接"),
    store_id: int | None = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return await _exchange(
        ExchangeRequest(code=code, store_id=store_id), user, db, platform=2, source=CardSource.douyin
    )


@router.post("/douyin", response_model=ResponseModel)
async def exchange_douyin_body(
    body: ExchangeRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """抖音扫码链接较长，推荐走 JSON body。"""
    return await _exchange(body, user, db, platform=2, source=CardSource.douyin)


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

    # 先占位：借助 coupon_code 唯一索引原子抢占券码，避免并发重复核销导致资损
    order = MeituanOrder(
        user_id=user.id,
        coupon_code=code,
        store_id=body.store_id,
        status=MeituanOrderStatus.pending,
    )
    db.add(order)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        dup = db.scalar(select(MeituanOrder).where(MeituanOrder.coupon_code == code))
        if dup and dup.status == MeituanOrderStatus.verified:
            raise HTTPException(status_code=400, detail="该券码已兑换")
        raise HTTPException(status_code=409, detail="该券码正在兑换中，请稍后重试")

    # 1) 仅 prepare，拿到 deal 信息后再决定是否正式核销（避免限兑用户把券核废）
    try:
        prepared, douyin_raw = await _prepare(platform, code)
    except ValueError as e:
        db.delete(order)
        db.commit()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        db.delete(order)
        db.commit()
        raise

    deal_id = str((prepared.get("ticketData") or {}).get("dealId", ""))
    ticket_name = prepared.get("ticketName") or (prepared.get("ticketData") or {}).get("dealTitle", "")
    mapping = get_mapping_by_deal_id(db, deal_id)
    if not mapping:
        reward_type, reward_value = guess_reward_from_name(ticket_name)
        mapping = MeituanDealMapping(
            store_id=body.store_id,
            deal_id=deal_id,
            deal_name=ticket_name,
            reward_type=reward_type,
            reward_value=reward_value,
            platform=platform,
            is_active=1,
            limit_per_user=guess_limit_per_user_from_name(ticket_name),
        )
        db.add(mapping)
        record_pending_deal(
            db,
            deal_id=deal_id,
            deal_name=ticket_name,
            platform=platform,
            coupon_code=code,
            ticket_data=prepared.get("ticketData"),
        )
        mark_pending_resolved_by_deal_id(db, deal_id)
        db.flush()
        db.refresh(mapping)
    elif not getattr(mapping, "limit_per_user", 0) and guess_limit_per_user_from_name(
        ticket_name or mapping.deal_name or ""
    ):
        # 存量映射补标限兑
        mapping.limit_per_user = 1
        db.flush()

    limit_n = mapping_limit_per_user(mapping, ticket_name or mapping.deal_name or "")
    if limit_n > 0 and deal_id:
        redeemed = user_redeemed_deal_count(db, user.id, deal_id)
        if redeemed >= limit_n:
            db.delete(order)
            db.commit()
            raise HTTPException(
                status_code=400,
                detail="该优惠每人限兑 1 次，您已兑换过。换手机号购买的券也无法重复兑换到同一微信账号。",
            )

    # 2) 正式核销
    try:
        consume_result = await _consume(platform, code, prepared, douyin_raw)
    except ValueError as e:
        db.delete(order)
        db.commit()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        db.delete(order)
        db.commit()
        raise

    ticket_data = prepared.get("ticketData") or {}
    voucher_expire = _parse_voucher_expire(ticket_data, platform)

    card = issue_period_card(
        db,
        user.id,
        mapping,
        source=source,
        receipt=code,
        store_id=body.store_id,
    )

    order.meituan_deal_id = deal_id
    order.deal_name = prepared.get("ticketName") or mapping.deal_name
    order.deal_type = mapping.reward_type.value
    order.store_id = body.store_id or mapping.store_id
    order.status = MeituanOrderStatus.verified
    order.verified_at = datetime.now()
    order.meituan_raw = {
        "result": consume_result,
        "ticketData": ticket_data,
        "voucherExpireDate": str(voucher_expire) if voucher_expire else None,
    }
    db.commit()
    db.refresh(card)

    validity = card_validity_api_fields(card)

    return ResponseModel(
        message=f"已成功兑换 {mapping.deal_name}",
        data={
            "card_id": card.id,
            "card_name": card.card_name,
            "card_type": card.card_type.value,
            "source": source.value,
            "start_date": str(card.start_date) if card.start_date else None,
            "end_date": str(card.end_date) if card.end_date else None,
            **validity,
            "voucher_expire_date": str(voucher_expire) if voucher_expire else None,
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
    items = []
    for r in rows:
        card = db.scalar(
            select(PeriodCard).where(
                PeriodCard.user_id == user.id,
                PeriodCard.meituan_receipt == r.coupon_code,
            )
        )
        validity = card_validity_api_fields(card) if card else {}
        voucher_expire = None
        if r.meituan_raw and isinstance(r.meituan_raw, dict):
            voucher_expire = r.meituan_raw.get("voucherExpireDate")
            if not voucher_expire and r.meituan_raw.get("ticketData"):
                vd = parse_voucher_expire_date(r.meituan_raw["ticketData"])
                voucher_expire = str(vd) if vd else None
        items.append(
            {
                "id": r.id,
                "deal_name": r.deal_name,
                "coupon_code": r.coupon_code,
                "status": r.status.value,
                "verified_at": r.verified_at.isoformat() if r.verified_at else None,
                "card_id": card.id if card else None,
                "start_date": str(card.start_date) if card and card.start_date else None,
                "end_date": str(card.end_date) if card and card.end_date else None,
                **validity,
                "voucher_expire_date": voucher_expire,
            }
        )
    return ResponseModel(data=items)
