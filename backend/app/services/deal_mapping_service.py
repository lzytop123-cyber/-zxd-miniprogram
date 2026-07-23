import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import MeituanDealMapping, PendingDealMapping, RewardType
from app.services.pass_days_parser import parse_pass_days_from_name
from app.services.card_service import get_mapping_by_deal_id


def guess_reward_from_name(name: str) -> tuple[RewardType, int]:
    """根据团购名称推断权益类型（供后台待配置项参考）。"""
    if not name:
        return RewardType.hours, 4
    pass_days = parse_pass_days_from_name(name)
    if "季卡" in name:
        return RewardType.quarter_pass, pass_days or 90
    if "上班族" in name and "月" in name:
        return RewardType.night_monthly, pass_days or 30
    if "晚自习" in name or ("夜" in name and "月" in name):
        return RewardType.night_monthly, pass_days or 30
    if "周卡" in name or (pass_days and "周" in name):
        return RewardType.week_pass, pass_days or 7
    if pass_days and re.search(r"月", name):
        return RewardType.month_pass, pass_days
    if "月卡" in name or re.search(r"\d+月", name):
        return RewardType.month_pass, pass_days or 30
    if "三天" in name or "3天" in name:
        return RewardType.day_pass, 3
    if "日卡" in name:
        return RewardType.day_pass, 1
    session_match = re.search(r"(\d+)次", name)
    if session_match or "次卡" in name:
        return RewardType.session, int(session_match.group(1)) if session_match else 10
    hours_match = re.search(r"(\d+)小时", name)
    if hours_match:
        return RewardType.hours, int(hours_match.group(1))
    if "四小时" in name or "4小时" in name:
        return RewardType.hours, 4
    if "小时" in name:
        return RewardType.hours, 4
    return RewardType.day_pass, 1


def guess_limit_per_user_from_name(name: str) -> int:
    """根据商品名判断是否「每微信用户限兑1次」（新客/限购/暑期双月等）。"""
    n = name or ""
    if "限购" in n:
        return 1
    if "新客专享" in n or "新客" in n:
        return 1
    if "暑期" in n and "双月" in n:
        return 1
    return 0


def mapping_limit_per_user(mapping: MeituanDealMapping | None, deal_name: str = "") -> int:
    """映射表优先；未配置时用商品名启发式。"""
    if mapping is not None:
        flagged = int(getattr(mapping, "limit_per_user", 0) or 0)
        if flagged > 0:
            return flagged
    return guess_limit_per_user_from_name(deal_name or (mapping.deal_name if mapping else "") or "")


def user_redeemed_deal_count(db: Session, user_id: int, deal_id: str) -> int:
    """该用户对该 deal_id 已成功核销次数。"""
    if not deal_id:
        return 0
    from app.models import MeituanOrder, MeituanOrderStatus
    from sqlalchemy import func

    return (
        db.scalar(
            select(func.count()).where(
                MeituanOrder.user_id == user_id,
                MeituanOrder.meituan_deal_id == deal_id,
                MeituanOrder.status == MeituanOrderStatus.verified,
            )
        )
        or 0
    )

def record_pending_deal(
    db: Session,
    *,
    deal_id: str,
    deal_name: str,
    platform: int,
    coupon_code: str,
    ticket_data: dict | None = None,
) -> None:
    """兑换缺映射时记录待配置 dealId（不核销券）。"""
    if get_mapping_by_deal_id(db, deal_id):
        return

    reward_type, reward_value = guess_reward_from_name(deal_name)
    row = db.scalar(
        select(PendingDealMapping).where(
            PendingDealMapping.deal_id == deal_id,
            PendingDealMapping.status == "pending",
        )
    )
    if row:
        row.deal_name = deal_name or row.deal_name
        row.last_coupon_code = coupon_code
        row.hit_count = (row.hit_count or 0) + 1
        row.ticket_snapshot = ticket_data or row.ticket_snapshot
        row.suggested_reward_type = reward_type
        row.suggested_reward_value = reward_value
    else:
        db.add(
            PendingDealMapping(
                deal_id=deal_id,
                deal_name=deal_name,
                platform=platform,
                last_coupon_code=coupon_code,
                ticket_snapshot=ticket_data,
                suggested_reward_type=reward_type,
                suggested_reward_value=reward_value,
                hit_count=1,
                status="pending",
            )
        )
    db.commit()


def resolve_pending_deal(
    db: Session,
    pending_id: int,
    *,
    store_id: int | None,
    reward_type: RewardType,
    reward_value: int | None,
    deal_name: str | None = None,
) -> MeituanDealMapping:
    pending = db.get(PendingDealMapping, pending_id)
    if not pending or pending.status != "pending":
        raise ValueError("待配置项不存在或已处理")

    existing = db.scalar(
        select(MeituanDealMapping).where(MeituanDealMapping.deal_id == pending.deal_id)
    )
    if existing:
        pending.status = "resolved"
        db.commit()
        return existing

    mapping = MeituanDealMapping(
        store_id=store_id,
        deal_id=pending.deal_id,
        deal_name=deal_name or pending.deal_name,
        reward_type=reward_type,
        reward_value=reward_value,
        platform=pending.platform or 1,
        is_active=1,
        limit_per_user=guess_limit_per_user_from_name(deal_name or pending.deal_name or ""),
    )
    db.add(mapping)
    pending.status = "resolved"
    db.commit()
    db.refresh(mapping)
    return mapping


def mark_pending_resolved_by_deal_id(db: Session, deal_id: str) -> None:
    rows = db.scalars(
        select(PendingDealMapping).where(
            PendingDealMapping.deal_id == str(deal_id),
            PendingDealMapping.status == "pending",
        )
    ).all()
    for row in rows:
        row.status = "resolved"
    if rows:
        db.commit()
