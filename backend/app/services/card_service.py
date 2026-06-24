from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    BillType,
    CardSource,
    CardType,
    MeituanDealMapping,
    PeriodCard,
    RewardType,
)
REWARD_TO_CARD: dict[RewardType, CardType] = {
    RewardType.hours: CardType.hourly,
    RewardType.day_pass: CardType.daily,
    RewardType.week_pass: CardType.weekly,
    RewardType.month_pass: CardType.monthly,
    RewardType.quarter_pass: CardType.quarterly,
    RewardType.night_monthly: CardType.night_monthly,
    RewardType.session: CardType.session,
}


def issue_period_card(
    db: Session,
    user_id: int,
    mapping: MeituanDealMapping,
    source: CardSource,
    receipt: str | None = None,
    store_id: int | None = None,
) -> PeriodCard:
    today = date.today()
    card_type = REWARD_TO_CARD.get(mapping.reward_type, CardType.custom)
    value = mapping.reward_value or 1

    card = PeriodCard(
        user_id=user_id,
        store_id=store_id or mapping.store_id,
        card_name=mapping.deal_name or mapping.reward_type.value,
        card_type=card_type,
        source=source,
        meituan_receipt=receipt,
        status=1,
    )

    if mapping.reward_type == RewardType.hours:
        card.remaining_hours = Decimal(str(value))
    elif mapping.reward_type == RewardType.session:
        card.total_sessions = value
        card.remaining_sessions = value
        card.start_date = today
        card.end_date = today + timedelta(days=364)
    elif mapping.reward_type == RewardType.night_monthly:
        card.start_date = today
        card.end_date = today + timedelta(days=value - 1)
        card.daily_start = mapping.night_start or datetime.strptime("18:00", "%H:%M").time()
        card.daily_end = mapping.night_end
    elif mapping.reward_type in (
        RewardType.day_pass,
        RewardType.week_pass,
        RewardType.month_pass,
        RewardType.quarter_pass,
    ):
        # 兑换即开卡，连续自然日有效，不可暂停
        card.start_date = today
        if mapping.reward_type == RewardType.day_pass and value > 1:
            card.end_date = today + timedelta(days=value - 1)
        else:
            days_map = {
                RewardType.day_pass: 0,
                RewardType.week_pass: 6,
                RewardType.month_pass: 29,
                RewardType.quarter_pass: 89,
            }
            card.end_date = today + timedelta(days=days_map.get(mapping.reward_type, value - 1))
    else:
        card.start_date = today
        card.end_date = today + timedelta(days=29)

    db.add(card)
    db.flush()
    return card


def _validate_reservation_within_card_period(
    card: PeriodCard,
    start_time: datetime,
    end_time: datetime,
) -> None:
    """期限卡（含月卡）：预约时段须在兑换后的有效期内。"""
    if not card.start_date and not card.end_date:
        return
    res_start = start_time.date()
    res_end = end_time.date()
    if card.start_date and res_start < card.start_date:
        raise ValueError(f"预约开始日期早于卡生效日（{card.start_date}）")
    if card.end_date and res_end > card.end_date:
        raise ValueError(f"预约结束日期超出卡有效期（{card.end_date}）")


def is_period_card_active(card: PeriodCard, today: date | None = None) -> bool:
    """卡是否仍可用于预约（已核销/已过期/额度用尽则不可用）。"""
    if card.status != 1:
        return False
    today = today or date.today()
    if card.end_date and card.end_date < today:
        return False
    if card.card_type == CardType.hourly:
        return bool(card.remaining_hours and card.remaining_hours > 0)
    if card.card_type == CardType.session:
        return bool(card.remaining_sessions and card.remaining_sessions > 0)
    return True


def _session_days(start_time: datetime, end_time: datetime) -> int:
    return (end_time.date() - start_time.date()).days + 1


def validate_period_card_for_reservation(
    db: Session,
    card: PeriodCard,
    reservation_bill_type: BillType,
    start_time: datetime,
    end_time: datetime,
    store_id: int,
) -> None:
    if card.status != 1:
        raise ValueError("期限卡已失效")
    today = date.today()
    if card.end_date and today > card.end_date:
        raise ValueError("期限卡已过期")
    if card.store_id and card.store_id != store_id:
        raise ValueError("该卡不适用于当前门店")

    if card.card_type == CardType.hourly:
        if reservation_bill_type != BillType.hourly:
            raise ValueError("小时卡仅可用于按小时预约")
        hours = Decimal(str((end_time - start_time).total_seconds() / 3600))
        if not card.remaining_hours or card.remaining_hours < hours:
            raise ValueError("小时卡余额不足")
        return

    if card.card_type == CardType.session:
        if reservation_bill_type != BillType.session:
            raise ValueError("次卡请使用「次卡」预约方式")
        if not card.remaining_sessions or card.remaining_sessions <= 0:
            raise ValueError("次卡次数已用完")
        if card.end_date and today > card.end_date:
            raise ValueError("次卡已过期")
        days = _session_days(start_time, end_time)
        if days < 1:
            raise ValueError("至少预约1天")
        if card.remaining_sessions < days:
            raise ValueError(f"次卡剩余 {card.remaining_sessions} 次，不足 {days} 天")
        _validate_reservation_within_card_period(card, start_time, end_time)
        return

    if card.card_type == CardType.night_monthly:
        if reservation_bill_type != BillType.night:
            raise ValueError("晚自习月卡仅可用于夜读预约")
        if card.daily_start:
            limit = card.daily_start
            if start_time.time() < limit:
                raise ValueError(f"晚自习月卡每日 {limit.strftime('%H:%M')} 后方可使用")
        _validate_reservation_within_card_period(card, start_time, end_time)
        return

    type_map = {
        CardType.daily: BillType.daily,
        CardType.monthly: BillType.monthly,
        CardType.weekly: BillType.weekly,
        CardType.quarterly: BillType.quarterly,
    }
    expected = type_map.get(card.card_type)
    if expected and reservation_bill_type != expected:
        raise ValueError("期限卡类型与预约方式不匹配")
    if card.card_type in (CardType.daily, CardType.monthly, CardType.weekly, CardType.quarterly):
        _validate_reservation_within_card_period(card, start_time, end_time)


def consume_period_card(
    db: Session,
    card: PeriodCard,
    reservation_bill_type: BillType,
    start_time: datetime,
    end_time: datetime,
    store_id: int,
) -> None:
    validate_period_card_for_reservation(
        db, card, reservation_bill_type, start_time, end_time, store_id
    )
    if card.card_type == CardType.hourly:
        hours = Decimal(str((end_time - start_time).total_seconds() / 3600)).quantize(Decimal("0.1"))
        card.remaining_hours -= hours
    elif card.card_type == CardType.session:
        days = _session_days(start_time, end_time)
        card.remaining_sessions -= days
    elif card.card_type == CardType.daily:
        # 天卡单次预约即核销
        card.status = 0
    elif card.card_type == CardType.weekly:
        # 周卡：完成一次预约即核销
        card.status = 0
    elif card.card_type == CardType.monthly:
        # 月卡：开卡后30天内完成一次预约即核销
        card.status = 0
    elif card.card_type == CardType.quarterly:
        card.status = 0
    elif card.card_type == CardType.night_monthly:
        card.status = 0
    if card.card_type == CardType.session and card.remaining_sessions <= 0:
        card.status = 0
    if card.card_type == CardType.hourly and card.remaining_hours <= 0:
        card.status = 0


def get_mapping_by_deal_id(db: Session, deal_id: str) -> MeituanDealMapping | None:
    return db.scalar(
        select(MeituanDealMapping).where(
            MeituanDealMapping.deal_id == str(deal_id),
            MeituanDealMapping.is_active == 1,
        )
    )
