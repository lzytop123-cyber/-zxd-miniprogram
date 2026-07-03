from datetime import date, datetime, time, timedelta
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
MULTI_USE_HOURLY_THRESHOLD = Decimal("50")

OFFICE_NIGHT_WEEKDAY_START = datetime.strptime("18:00", "%H:%M").time()
OFFICE_NIGHT_WEEKDAY_END = datetime.strptime("23:30", "%H:%M").time()
OFFICE_NIGHT_WEEKEND_START = datetime.strptime("07:30", "%H:%M").time()
OFFICE_NIGHT_WEEKEND_END = datetime.strptime("23:30", "%H:%M").time()
OFFICE_NIGHT_USAGE_RULE = "默认30天固定座位 · 工作日 18:00-23:30 · 周末 7:30-23:30 可使用"
OFFICE_NIGHT_MAX_DAYS = 30


def validate_office_night_reservation(start_time: datetime, end_time: datetime) -> None:
    """夜读月卡：预约整段日期（最长30天）；每日可用时段在入座/开门时校验。"""
    if end_time <= start_time:
        raise ValueError("结束日期须晚于开始日期")
    days = (end_time.date() - start_time.date()).days + 1
    if days > OFFICE_NIGHT_MAX_DAYS:
        raise ValueError(f"夜读月卡单次预约最长 {OFFICE_NIGHT_MAX_DAYS} 天")


def is_office_night_monthly_card(card: PeriodCard) -> bool:
    """上班族/晚自习月卡（含历史误发为 monthly 的同名额卡）。"""
    if card.card_type == CardType.night_monthly:
        return True
    name = card.card_name or ""
    return card.card_type == CardType.monthly and ("上班族" in name or "晚自习" in name)


def night_window_for_date(day: date) -> tuple[time, time, str]:
    if day.weekday() < 5:
        return OFFICE_NIGHT_WEEKDAY_START, OFFICE_NIGHT_WEEKDAY_END, "工作日"
    return OFFICE_NIGHT_WEEKEND_START, OFFICE_NIGHT_WEEKEND_END, "周末"


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
        hours = Decimal(str(value))
        card.remaining_hours = hours
        card.total_hours = hours
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


def daily_pass_days(card: PeriodCard) -> int:
    """天卡覆盖的连续自然日数（如三天卡为 3，日卡为 1）。"""
    if card.card_type != CardType.daily:
        return 0
    if card.start_date and card.end_date:
        return (card.end_date - card.start_date).days + 1
    return 1


def _validate_daily_pass_reservation(
    card: PeriodCard,
    start_time: datetime,
    end_time: datetime,
) -> None:
    span = daily_pass_days(card)
    res_start = start_time.date()
    res_end = end_time.date()
    if span > 1:
        if res_start != card.start_date or res_end != card.end_date:
            raise ValueError(
                f"该卡须连续使用 {span} 天（{card.start_date} 至 {card.end_date}），请按完整时段预约"
            )
        return
    if _session_days(start_time, end_time) != 1:
        raise ValueError("日卡须预约单日")
    _validate_reservation_within_card_period(card, start_time, end_time)


def _reservation_hours(start_time: datetime, end_time: datetime) -> Decimal:
    return Decimal(str((end_time - start_time).total_seconds() / 3600)).quantize(Decimal("0.1"))


def hourly_allows_partial_use(card: PeriodCard) -> bool:
    """仅 50 小时档支持多次预约按实际时长扣减；其余小时卡须一次性约满剩余时长。"""
    if card.total_hours is not None:
        return card.total_hours >= MULTI_USE_HOURLY_THRESHOLD
    remaining = card.remaining_hours or Decimal(0)
    if remaining >= MULTI_USE_HOURLY_THRESHOLD:
        return True
    name = card.card_name or ""
    return "50" in name and "小时" in name


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
        hours = _reservation_hours(start_time, end_time)
        remaining = (card.remaining_hours or Decimal(0)).quantize(Decimal("0.1"))
        if hourly_allows_partial_use(card):
            if remaining < hours:
                raise ValueError("小时卡余额不足")
        elif hours != remaining:
            raise ValueError(f"该小时卡须一次性用完，请预约 {remaining} 小时")
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

    if is_office_night_monthly_card(card):
        if reservation_bill_type != BillType.night:
            raise ValueError("该月卡请使用「夜读」预约方式选座")
        validate_office_night_reservation(start_time, end_time)
        _validate_reservation_within_card_period(card, start_time, end_time)
        return

    if card.card_type == CardType.daily:
        if reservation_bill_type != BillType.daily:
            raise ValueError("天卡请使用「天卡」预约方式")
        _validate_daily_pass_reservation(card, start_time, end_time)
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
    if card.card_type in (CardType.monthly, CardType.weekly, CardType.quarterly):
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
        if hourly_allows_partial_use(card):
            hours = _reservation_hours(start_time, end_time)
            card.remaining_hours = (card.remaining_hours - hours).quantize(Decimal("0.1"))
        else:
            card.remaining_hours = Decimal("0")
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


def refund_period_card_consume(
    card: PeriodCard,
    reservation_bill_type: BillType,
    start_time: datetime,
    end_time: datetime,
) -> None:
    """取消预约时回滚期限卡消耗（与 consume_period_card 对应）。"""
    if card.card_type == CardType.hourly:
        if hourly_allows_partial_use(card):
            hours = _reservation_hours(start_time, end_time)
            card.remaining_hours = ((card.remaining_hours or Decimal(0)) + hours).quantize(Decimal("0.1"))
        else:
            # 一次性小时卡：恢复全部时长
            card.remaining_hours = card.total_hours or card.remaining_hours
        card.status = 1
    elif card.card_type == CardType.session:
        days = _session_days(start_time, end_time)
        card.remaining_sessions = (card.remaining_sessions or 0) + days
        card.status = 1
    else:
        # 天/周/月/季/夜读月卡：单次预约即核销，取消后恢复可用
        card.status = 1


def get_mapping_by_deal_id(db: Session, deal_id: str) -> MeituanDealMapping | None:
    return db.scalar(
        select(MeituanDealMapping).where(
            MeituanDealMapping.deal_id == str(deal_id),
            MeituanDealMapping.is_active == 1,
        )
    )


PURCHASABLE_BILL_TYPES = frozenset({
    BillType.daily,
    BillType.weekly,
    BillType.monthly,
    BillType.quarterly,
    BillType.session,
    BillType.night_monthly,
})

BILL_TYPE_LABELS = {
    BillType.daily: "天卡",
    BillType.weekly: "周卡",
    BillType.monthly: "月卡",
    BillType.quarterly: "季卡",
    BillType.session: "次卡",
    BillType.night_monthly: "夜读月卡",
}


def _reward_from_pricing_rule(rule) -> tuple[RewardType, int]:
    bt = rule.bill_type
    if bt == BillType.daily:
        return RewardType.day_pass, rule.valid_days or 1
    if bt == BillType.weekly:
        return RewardType.week_pass, rule.valid_days or 7
    if bt == BillType.monthly:
        return RewardType.month_pass, rule.valid_days or 30
    if bt == BillType.quarterly:
        return RewardType.quarter_pass, rule.valid_days or 90
    if bt == BillType.session:
        return RewardType.session, rule.valid_days or 10
    if bt == BillType.night_monthly:
        return RewardType.night_monthly, rule.valid_days or 30
    raise ValueError("该套餐不支持在线购买")


def issue_period_card_from_pricing(
    db: Session,
    user_id: int,
    store_id: int,
    rule,
    receipt: str | None = None,
) -> PeriodCard:
    from types import SimpleNamespace

    reward_type, reward_value = _reward_from_pricing_rule(rule)
    label = BILL_TYPE_LABELS.get(rule.bill_type, rule.bill_type.value)
    deal_name = (rule.remark or label).strip() or label
    mapping = SimpleNamespace(
        deal_name=deal_name,
        reward_type=reward_type,
        reward_value=reward_value,
        store_id=store_id,
        night_start=rule.night_start,
        night_end=rule.night_end,
    )
    return issue_period_card(
        db,
        user_id,
        mapping,
        CardSource.purchase,
        receipt=receipt,
        store_id=store_id,
    )


def fulfill_card_purchase(db: Session, order) -> PeriodCard:
    """支付成功后发卡（幂等）。"""
    from app.models import CardPurchaseOrder, PricingRule

    if order.period_card_id:
        card = db.get(PeriodCard, order.period_card_id)
        if card:
            return card
    rule = db.get(PricingRule, order.pricing_rule_id)
    if not rule:
        raise ValueError("定价规则不存在")
    card = issue_period_card_from_pricing(
        db,
        order.user_id,
        order.store_id,
        rule,
        receipt=order.order_no,
    )
    order.period_card_id = card.id
    order.pay_status = 1
    return card
