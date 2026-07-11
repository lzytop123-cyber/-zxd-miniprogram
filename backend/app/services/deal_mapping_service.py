import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import MeituanDealMapping, PendingDealMapping, RewardType
from app.services.card_service import get_mapping_by_deal_id


def guess_reward_from_name(name: str) -> tuple[RewardType, int]:
    """根据团购名称推断权益类型（供后台待配置项参考）。"""
    if not name:
        return RewardType.hours, 4
    if "季卡" in name:
        return RewardType.quarter_pass, 90
    if re.search(r"双月|两个月|2个月", name):
        return RewardType.month_pass, 60
    if re.search(r"四个月|4个月", name):
        return RewardType.month_pass, 120
    if re.search(r"三个月|3个月", name):
        return RewardType.month_pass, 90
    if "上班族" in name and "月" in name:
        return RewardType.night_monthly, 30
    if "晚自习" in name or ("夜" in name and "月" in name):
        return RewardType.night_monthly, 30
    if "月卡" in name:
        return RewardType.month_pass, 30
    if "周卡" in name:
        return RewardType.week_pass, 7
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
