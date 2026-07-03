"""期限卡核销规则单元测试（无需启动服务）。"""

from datetime import datetime, timedelta

from decimal import Decimal

from app.models import BillType, CardType, PeriodCard
from app.services.card_service import (
    _session_days,
    consume_period_card,
    hourly_allows_partial_use,
    validate_period_card_for_reservation,
)


def _card(card_type: CardType, **kwargs) -> PeriodCard:
    today = datetime.now().date()
    card = PeriodCard(
        user_id=1,
        card_name="test",
        card_type=card_type,
        status=1,
        start_date=today,
        end_date=today + timedelta(days=30),
        **kwargs,
    )
    return card


def test_session_multi_day_deduct():
    card = _card(CardType.session, remaining_sessions=10)
    start = datetime(2026, 6, 24, 0, 0, 0)
    end = datetime(2026, 6, 26, 23, 59, 59)
    assert _session_days(start, end) == 3
    consume_period_card(None, card, BillType.session, start, end, 1)
    assert card.remaining_sessions == 7


def test_weekly_one_shot():
    card = _card(CardType.weekly)
    start = datetime(2026, 6, 24, 0, 0, 0)
    end = datetime(2026, 6, 30, 23, 59, 59)
    consume_period_card(None, card, BillType.weekly, start, end, 1)
    assert card.status == 0


def test_quarterly_bill_type():
    card = _card(CardType.quarterly)
    card.end_date = datetime.now().date() + timedelta(days=89)
    start = datetime(2026, 6, 24, 0, 0, 0)
    end = datetime(2026, 9, 21, 23, 59, 59)
    validate_period_card_for_reservation(None, card, BillType.quarterly, start, end, 1)
    try:
        validate_period_card_for_reservation(None, card, BillType.monthly, start, end, 1)
        raise AssertionError("季卡不应匹配月卡预约")
    except ValueError as e:
        assert "不匹配" in str(e)


def test_hourly_single_use_must_match_remaining():
    card = _card(CardType.hourly, remaining_hours=Decimal("4"), total_hours=Decimal("4"))
    start = datetime(2026, 6, 24, 9, 0, 0)
    end = datetime(2026, 6, 24, 11, 0, 0)
    try:
        validate_period_card_for_reservation(None, card, BillType.hourly, start, end, 1)
        raise AssertionError("4小时卡不应允许2小时预约")
    except ValueError as e:
        assert "一次性" in str(e)

    end4 = datetime(2026, 6, 24, 13, 0, 0)
    validate_period_card_for_reservation(None, card, BillType.hourly, start, end4, 1)
    consume_period_card(None, card, BillType.hourly, start, end4, 1)
    assert card.remaining_hours == Decimal("0")
    assert card.status == 0


def test_hourly_50h_partial_use():
    card = _card(CardType.hourly, remaining_hours=Decimal("50"), total_hours=Decimal("50"))
    start = datetime(2026, 6, 24, 9, 0, 0)
    end = datetime(2026, 6, 24, 11, 0, 0)
    assert hourly_allows_partial_use(card)
    consume_period_card(None, card, BillType.hourly, start, end, 1)
    assert card.remaining_hours == Decimal("48.0")
    assert card.status == 1


def test_daily_pass_three_day_continuous():
    from datetime import date, time, timedelta

    today = date.today()
    card = PeriodCard(
        user_id=1,
        card_name="三天卡",
        card_type=CardType.daily,
        status=1,
        start_date=today,
        end_date=today + timedelta(days=2),
    )
    start = datetime.combine(today, time.min)
    end = datetime.combine(today + timedelta(days=2), time(23, 59, 59))
    validate_period_card_for_reservation(None, card, BillType.daily, start, end, 1)
    consume_period_card(None, card, BillType.daily, start, end, 1)
    assert card.status == 0

    card2 = PeriodCard(
        user_id=1,
        card_name="三天卡",
        card_type=CardType.daily,
        status=1,
        start_date=today,
        end_date=today + timedelta(days=2),
    )
    bad_end = datetime.combine(today, time(23, 59, 59))
    try:
        validate_period_card_for_reservation(None, card2, BillType.daily, start, bad_end, 1)
        raise AssertionError("三天卡不应允许只约1天")
    except ValueError as e:
        assert "连续使用" in str(e)


def test_office_night_weekday_window():
    from datetime import time

    card = PeriodCard(
        user_id=1,
        card_name="「上班族」月卡",
        card_type=CardType.night_monthly,
        status=1,
        start_date=datetime(2026, 7, 6).date(),  # Monday
        end_date=datetime(2026, 8, 4).date(),
    )
    start = datetime(2026, 7, 6, 18, 0, 0)
    end = datetime(2026, 7, 6, 23, 30, 0)
    validate_period_card_for_reservation(None, card, BillType.night, start, end, 1)

    too_early = datetime(2026, 7, 6, 17, 30, 0)
    try:
        validate_period_card_for_reservation(None, card, BillType.night, too_early, end, 1)
        raise AssertionError("工作日不应允许17:30开始")
    except ValueError as e:
        assert "工作日" in str(e)


def test_office_night_weekend_window():
    card = PeriodCard(
        user_id=1,
        card_name="知行岛晚自习月卡",
        card_type=CardType.night_monthly,
        status=1,
        start_date=datetime(2026, 7, 4).date(),  # Saturday
        end_date=datetime(2026, 8, 3).date(),
    )
    start = datetime(2026, 7, 4, 7, 30, 0)
    end = datetime(2026, 7, 4, 23, 30, 0)
    validate_period_card_for_reservation(None, card, BillType.night, start, end, 1)


def test_legacy_monthly_office_card_uses_night_bill():
    card = PeriodCard(
        user_id=1,
        card_name="「上班族」月卡",
        card_type=CardType.monthly,
        status=1,
        start_date=datetime(2026, 7, 6).date(),
        end_date=datetime(2026, 8, 4).date(),
    )
    start = datetime(2026, 7, 6, 18, 0, 0)
    end = datetime(2026, 7, 6, 23, 0, 0)
    validate_period_card_for_reservation(None, card, BillType.night, start, end, 1)
    try:
        validate_period_card_for_reservation(None, card, BillType.monthly, start, end, 1)
        raise AssertionError("上班族月卡不应走普通月卡预约")
    except ValueError as e:
        assert "夜读" in str(e)


if __name__ == "__main__":
    test_session_multi_day_deduct()
    test_weekly_one_shot()
    test_quarterly_bill_type()
    test_hourly_single_use_must_match_remaining()
    test_hourly_50h_partial_use()
    test_daily_pass_three_day_continuous()
    test_office_night_weekday_window()
    test_office_night_weekend_window()
    test_legacy_monthly_office_card_uses_night_bill()
    print("All card rule tests passed.")
