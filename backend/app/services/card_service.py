from datetime import date, datetime, time, timedelta
from decimal import Decimal
import re

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
from app.services.store_hours import (
    OFFICE_NIGHT_BOOKING_HINT,
    OFFICE_NIGHT_USAGE_RULE,
    OFFICE_NIGHT_WEEKDAY_END,
    OFFICE_NIGHT_WEEKDAY_START,
    night_seat_block_window_for_date,
    night_window_for_date,
)

MULTI_USE_HOURLY_THRESHOLD = Decimal("50")
OFFICE_NIGHT_MAX_DAYS = 30
OFFICE_NIGHT_BILL_TYPES = frozenset({BillType.night, BillType.night_monthly})

# 卡面效期（自然日，含兑换日）。详见 app/data/deal_templates.py
HOURLY_VALIDITY_DAYS: dict[int, int] = {4: 90, 50: 180}
DEFAULT_HOURLY_VALIDITY_DAYS = 90
SESSION_VALIDITY_DAYS: dict[int, int] = {10: 90, 30: 360}
DEFAULT_SESSION_VALIDITY_DAYS = 90
DAILY_PASS_VALIDITY_DAYS = 90
MULTI_DAY_PASS_VALIDITY_DAYS = 15
WEEKLY_PASS_VALIDITY_DAYS = 90
WEEKLY_PASS_CONSECUTIVE_DAYS = 7
MONTHLY_PASS_VALIDITY_DAYS = 180
MONTHLY_PASS_CONSECUTIVE_DAYS = 30
QUARTERLY_PASS_VALIDITY_DAYS = 180
NIGHT_MONTHLY_VALIDITY_DAYS = 90
LEGACY_FIXED_USAGE_WINDOW_MAX_DAYS = 7


def validity_days_for_reward(reward_type: RewardType, value: int) -> int | None:
    """兑换后卡面效期天数（None 表示不写日期）。"""
    if reward_type == RewardType.hours:
        return HOURLY_VALIDITY_DAYS.get(value, DEFAULT_HOURLY_VALIDITY_DAYS)
    if reward_type == RewardType.session:
        return SESSION_VALIDITY_DAYS.get(value, DEFAULT_SESSION_VALIDITY_DAYS)
    if reward_type == RewardType.day_pass:
        return MULTI_DAY_PASS_VALIDITY_DAYS if value > 1 else DAILY_PASS_VALIDITY_DAYS
    if reward_type == RewardType.week_pass:
        return WEEKLY_PASS_VALIDITY_DAYS
    if reward_type == RewardType.month_pass:
        return MONTHLY_PASS_VALIDITY_DAYS
    if reward_type == RewardType.quarter_pass:
        return QUARTERLY_PASS_VALIDITY_DAYS
    if reward_type == RewardType.night_monthly:
        return NIGHT_MONTHLY_VALIDITY_DAYS
    return None


def _set_card_validity(card: PeriodCard, today: date, valid_days: int) -> None:
    card.start_date = today
    card.end_date = today + timedelta(days=valid_days - 1)


def card_validity_api_fields(card: PeriodCard, today: date | None = None) -> dict:
    """卡面效期字段，供小程序/后台展示。"""
    today = today or date.today()
    start = str(card.start_date) if card.start_date else None
    end = str(card.end_date) if card.end_date else None
    remain = (card.end_date - today).days if card.end_date else None
    if start and end:
        validity_range = f"{start} ~ {end}"
    elif end:
        validity_range = f"至 {end}"
    elif start:
        validity_range = f"{start} 起"
    else:
        validity_range = None
    return {
        "validity_range": validity_range,
        "validity_days_remaining": remain,
    }


def validate_office_night_reservation(start_time: datetime, end_time: datetime) -> None:
    """夜读/上班族月卡：须一次预约连续 30 天；每日可用时段在入座/开门时校验。"""
    if end_time <= start_time:
        raise ValueError("结束日期须晚于开始日期")
    days = (end_time.date() - start_time.date()).days + 1
    if days != OFFICE_NIGHT_MAX_DAYS:
        raise ValueError(f"夜读月卡须预约连续 {OFFICE_NIGHT_MAX_DAYS} 天")


def _normalize_card_name(name: str | None) -> str:
    return (name or "").replace(" ", "").replace("　", "")


def infer_pass_days_from_card_name(name: str | None) -> int | None:
    """从卡名识别双月/多月规格（兼容映射填错为 30 的旧卡）。"""
    text = _normalize_card_name(name)
    if not text:
        return None
    if re.search(r"双月|两个月|2个月", text):
        return 60
    if re.search(r"四个月|4个月", text):
        return 120
    if re.search(r"三个月|3个月", text):
        return 90
    return None


def repair_monthly_pass_days_from_name(card: PeriodCard) -> bool:
    if card.card_type != CardType.monthly or is_office_night_monthly_card(card):
        return False
    inferred = infer_pass_days_from_card_name(card.card_name)
    if not inferred or card.total_sessions == inferred:
        return False
    card.total_sessions = inferred
    return True


def is_office_night_monthly_card(card: PeriodCard) -> bool:
    """上班族/晚自习月卡（含历史误发为 monthly 的同名额卡）。"""
    if card.card_type == CardType.night_monthly:
        return True
    if card.card_type != CardType.monthly:
        return False
    name = _normalize_card_name(card.card_name)
    if any(k in name for k in ("上班族", "晚自习", "夜读")):
        return True
    # 误发为 monthly 的夜读卡兑换时会写入 daily_start
    return card.daily_start is not None


def ensure_office_night_card_type(db: Session | None, card: PeriodCard) -> None:
    """将误发为 monthly 的上班族/夜读月卡纠正为 night_monthly。"""
    if card.card_type != CardType.monthly or not is_office_night_monthly_card(card):
        return
    card.card_type = CardType.night_monthly
    if not card.daily_start:
        card.daily_start = OFFICE_NIGHT_WEEKDAY_START
    if not card.daily_end:
        card.daily_end = OFFICE_NIGHT_WEEKDAY_END
    if db is not None:
        db.flush()


REWARD_TO_CARD: dict[RewardType, CardType] = {
    RewardType.hours: CardType.hourly,
    RewardType.day_pass: CardType.daily,
    RewardType.week_pass: CardType.weekly,
    RewardType.month_pass: CardType.monthly,
    RewardType.quarter_pass: CardType.quarterly,
    RewardType.night_monthly: CardType.night_monthly,
    RewardType.session: CardType.session,
}


def repair_misissued_card_validity(card: PeriodCard) -> bool:
    """老数据：效期被误写成预约跨度（7/30天），导致无法在效期内约满连续天数。"""
    if not card.start_date or not card.end_date or card.status != 1:
        return False
    window = (card.end_date - card.start_date).days + 1
    expected: int | None = None
    need_span = 1
    if is_office_night_monthly_card(card) or card.card_type == CardType.night_monthly:
        expected = NIGHT_MONTHLY_VALIDITY_DAYS
        need_span = OFFICE_NIGHT_MAX_DAYS
    elif card.card_type == CardType.monthly:
        expected = MONTHLY_PASS_VALIDITY_DAYS
        need_span = monthly_pass_days(card) or MONTHLY_PASS_CONSECUTIVE_DAYS
    elif card.card_type == CardType.weekly:
        expected = WEEKLY_PASS_VALIDITY_DAYS
        need_span = WEEKLY_PASS_CONSECUTIVE_DAYS
    else:
        return False
    if window >= expected:
        return False
    # 效期窗口不足以完成一次预约，或误把「连续天数」当成效期
    if window < need_span or window <= need_span + 1:
        card.end_date = card.start_date + timedelta(days=expected - 1)
        return True
    return False


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
        days = validity_days_for_reward(RewardType.hours, value)
        if days:
            _set_card_validity(card, today, days)
    elif mapping.reward_type == RewardType.session:
        card.total_sessions = value
        card.remaining_sessions = value
        days = validity_days_for_reward(RewardType.session, value)
        if days:
            _set_card_validity(card, today, days)
    elif mapping.reward_type == RewardType.night_monthly:
        days = validity_days_for_reward(RewardType.night_monthly, value)
        if days:
            _set_card_validity(card, today, days)
        card.total_sessions = value or OFFICE_NIGHT_MAX_DAYS
        card.daily_start = mapping.night_start or OFFICE_NIGHT_WEEKDAY_START
        card.daily_end = mapping.night_end
    elif mapping.reward_type in (
        RewardType.day_pass,
        RewardType.week_pass,
        RewardType.month_pass,
        RewardType.quarter_pass,
    ):
        days = validity_days_for_reward(mapping.reward_type, value)
        if days:
            _set_card_validity(card, today, days)
        if mapping.reward_type == RewardType.day_pass and value > 1:
            card.total_sessions = value
        elif mapping.reward_type == RewardType.week_pass:
            card.total_sessions = value or WEEKLY_PASS_CONSECUTIVE_DAYS
        elif mapping.reward_type == RewardType.month_pass:
            card.total_sessions = value or MONTHLY_PASS_CONSECUTIVE_DAYS
        elif mapping.reward_type == RewardType.quarter_pass:
            card.total_sessions = value or 90
    else:
        _set_card_validity(card, today, 30)

    db.add(card)
    db.flush()
    return card


def _validate_reservation_within_card_period(
    card: PeriodCard,
    start_time: datetime,
    end_time: datetime,
) -> None:
    """预约整段须在卡有效期内（次卡/夜读/日卡等）。"""
    if not card.start_date and not card.end_date:
        return
    res_start = start_time.date()
    res_end = end_time.date()
    if card.start_date and res_start < card.start_date:
        raise ValueError(f"预约开始日期早于卡生效日（{card.start_date}）")
    if card.end_date and res_end > card.end_date:
        raise ValueError(f"预约结束日期超出卡有效期（{card.end_date}）")


def office_night_pass_days(card: PeriodCard) -> int:
    if not is_office_night_monthly_card(card):
        return 0
    if card.total_sessions and card.total_sessions > 1:
        return card.total_sessions
    return OFFICE_NIGHT_MAX_DAYS


def monthly_pass_days(card: PeriodCard) -> int:
    if card.card_type != CardType.monthly:
        return 0
    inferred = infer_pass_days_from_card_name(card.card_name)
    if inferred:
        return inferred
    if card.total_sessions and card.total_sessions > 1:
        return card.total_sessions
    return MONTHLY_PASS_CONSECUTIVE_DAYS


def quarterly_pass_days(card: PeriodCard) -> int:
    if card.card_type != CardType.quarterly:
        return 0
    if card.total_sessions and card.total_sessions > 1:
        return card.total_sessions
    return 90


def period_pass_days(card: PeriodCard) -> int:
    """周期卡须一次约满的连续自然日数（随团购映射 reward_value 变化）。"""
    if is_office_night_monthly_card(card) or card.card_type == CardType.night_monthly:
        return office_night_pass_days(card)
    if card.card_type == CardType.weekly:
        return weekly_pass_days(card)
    if card.card_type == CardType.monthly:
        return monthly_pass_days(card)
    if card.card_type == CardType.quarterly:
        return quarterly_pass_days(card)
    return 0


def weekly_pass_days(card: PeriodCard) -> int:
    if card.card_type != CardType.weekly:
        return 0
    if card.total_sessions and card.total_sessions > 1:
        return card.total_sessions
    return WEEKLY_PASS_CONSECUTIVE_DAYS


def _validate_consecutive_pass_in_validity(
    card: PeriodCard,
    start_time: datetime,
    end_time: datetime,
    span: int,
) -> None:
    """效期内须一次预约连续 span 天（三天卡、周卡）。"""
    today = date.today()
    if card.end_date and today > card.end_date:
        raise ValueError("期限卡已过期")
    days = _session_days(start_time, end_time)
    if days != span:
        raise ValueError(f"须预约连续 {span} 天")
    res_start = start_time.date()
    res_end = end_time.date()
    if card.start_date and res_start < card.start_date:
        raise ValueError(f"预约开始日期早于卡生效日（{card.start_date}）")
    if card.end_date and res_start > card.end_date:
        raise ValueError(f"须在 {card.end_date} 前开始预约")
    if card.end_date and res_end > card.end_date:
        raise ValueError(f"预约结束日期超出卡有效期（{card.end_date}）")


def _validate_booking_starts_within_validity(
    card: PeriodCard,
    start_time: datetime,
    now: datetime | None = None,
) -> None:
    """周/月/季卡：须在卡面有效期内开始预约；预约时长由套餐决定。"""
    now = now or datetime.now()
    today = now.date()
    res_start = start_time.date()
    if card.end_date and today > card.end_date:
        raise ValueError("期限卡已过期")
    if card.start_date and res_start < card.start_date:
        raise ValueError(f"预约开始日期早于卡生效日（{card.start_date}）")
    if card.end_date and res_start > card.end_date:
        raise ValueError(f"须在 {card.end_date} 前开始预约")


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
    """天卡单次可用连续自然日数（如三天卡为 3，日卡为 1）。"""
    if card.card_type != CardType.daily:
        return 0
    if card.total_sessions and card.total_sessions > 1:
        return card.total_sessions
    if card.start_date and card.end_date:
        span = (card.end_date - card.start_date).days + 1
        if span <= LEGACY_FIXED_USAGE_WINDOW_MAX_DAYS:
            return span
    return 1


def _validate_daily_pass_reservation(
    card: PeriodCard,
    start_time: datetime,
    end_time: datetime,
) -> None:
    span = daily_pass_days(card)
    res_start = start_time.date()
    res_end = end_time.date()
    if span > 1 and card.start_date and card.end_date:
        window = (card.end_date - card.start_date).days + 1
        if window > LEGACY_FIXED_USAGE_WINDOW_MAX_DAYS:
            _validate_consecutive_pass_in_validity(card, start_time, end_time, span)
            return
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


def hourly_allows_multi_booking(card: PeriodCard) -> bool:
    """50 小时档支持多次预约、按实际时长扣减。"""
    if card.total_hours is not None:
        return card.total_hours >= MULTI_USE_HOURLY_THRESHOLD
    remaining = card.remaining_hours or Decimal(0)
    if remaining >= MULTI_USE_HOURLY_THRESHOLD:
        return True
    name = card.card_name or ""
    return "50" in name and "小时" in name


def hourly_allows_partial_use(card: PeriodCard) -> bool:
    """兼容旧名：是否多次预约扣减。"""
    return hourly_allows_multi_booking(card)


def validate_period_card_for_reservation(
    db: Session,
    card: PeriodCard,
    reservation_bill_type: BillType,
    start_time: datetime,
    end_time: datetime,
    store_id: int,
) -> None:
    repair_misissued_card_validity(card)
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
        if card.end_date and today > card.end_date:
            raise ValueError("小时卡已过期")
        hours = _reservation_hours(start_time, end_time)
        remaining = (card.remaining_hours or Decimal(0)).quantize(Decimal("0.1"))
        if hours <= 0:
            raise ValueError("预约时长须大于 0")
        if remaining < hours:
            raise ValueError(f"预约时长不能超过卡面余额（剩余 {remaining} 小时）")
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

    ensure_office_night_card_type(db, card)
    if is_office_night_monthly_card(card):
        if reservation_bill_type not in OFFICE_NIGHT_BILL_TYPES:
            raise ValueError("该月卡请使用「夜读」预约方式选座")
        _validate_consecutive_pass_in_validity(
            card, start_time, end_time, office_night_pass_days(card)
        )
        return

    if card.card_type == CardType.daily:
        if reservation_bill_type != BillType.daily:
            raise ValueError("天卡请使用「天卡」预约方式")
        _validate_daily_pass_reservation(card, start_time, end_time)
        return

    if card.card_type == CardType.weekly:
        if reservation_bill_type != BillType.weekly:
            raise ValueError("周卡请使用「周卡」预约方式")
        _validate_consecutive_pass_in_validity(
            card, start_time, end_time, weekly_pass_days(card)
        )
        return

    if card.card_type == CardType.monthly:
        if reservation_bill_type != BillType.monthly:
            raise ValueError("月卡请使用「月卡」预约方式")
        _validate_consecutive_pass_in_validity(
            card, start_time, end_time, monthly_pass_days(card)
        )
        return

    type_map = {
        CardType.daily: BillType.daily,
        CardType.monthly: BillType.monthly,
        CardType.weekly: BillType.weekly,
        CardType.quarterly: BillType.quarterly,
    }
    expected = type_map.get(card.card_type)
    if expected and reservation_bill_type != expected:
        if reservation_bill_type in OFFICE_NIGHT_BILL_TYPES:
            raise ValueError("该月卡请使用「夜读」预约方式选座")
        raise ValueError("期限卡类型与预约方式不匹配")
    if card.card_type == CardType.quarterly:
        if reservation_bill_type != BillType.quarterly:
            raise ValueError("季卡请使用「季卡」预约方式")
        span = quarterly_pass_days(card)
        if span > 1:
            _validate_consecutive_pass_in_validity(card, start_time, end_time, span)
        else:
            _validate_booking_starts_within_validity(card, start_time)
        return


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
        if hourly_allows_multi_booking(card):
            hours = _reservation_hours(start_time, end_time)
            card.remaining_hours = (card.remaining_hours - hours).quantize(Decimal("0.1"))
        else:
            # 一次性小时卡：可约少于面额，核销后整张失效
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
    elif is_office_night_monthly_card(card) or card.card_type == CardType.night_monthly:
        card.status = 0
    elif card.card_type == CardType.monthly:
        card.status = 0
    elif card.card_type == CardType.quarterly:
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
        if hourly_allows_multi_booking(card):
            hours = _reservation_hours(start_time, end_time)
            card.remaining_hours = ((card.remaining_hours or Decimal(0)) + hours).quantize(Decimal("0.1"))
            if card.status == 0 and card.remaining_hours > 0:
                card.status = 1
        else:
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
