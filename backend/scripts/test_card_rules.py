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


def test_office_night_monthly_period():
    card = PeriodCard(
        user_id=1,
        card_name="「上班族」月卡",
        card_type=CardType.night_monthly,
        status=1,
        start_date=datetime(2026, 7, 3).date(),
        end_date=datetime(2026, 8, 1).date(),
    )
    start = datetime(2026, 7, 3, 0, 0, 0)
    end = datetime(2026, 8, 1, 23, 59, 59)
    validate_period_card_for_reservation(None, card, BillType.night, start, end, 1)


def test_office_night_rejects_over_30_days():
    card = PeriodCard(
        user_id=1,
        card_name="知行岛晚自习月卡",
        card_type=CardType.night_monthly,
        status=1,
        start_date=datetime(2026, 7, 3).date(),
        end_date=datetime(2026, 9, 1).date(),
    )
    start = datetime(2026, 7, 3, 0, 0, 0)
    end = datetime(2026, 8, 3, 23, 59, 59)
    try:
        validate_period_card_for_reservation(None, card, BillType.night, start, end, 1)
        raise AssertionError("不应超过30天")
    except ValueError as e:
        assert "30" in str(e)


def test_legacy_monthly_office_card_uses_night_bill():
    card = PeriodCard(
        user_id=1,
        card_name="「上班族」月卡",
        card_type=CardType.monthly,
        status=1,
        start_date=datetime(2026, 7, 3).date(),
        end_date=datetime(2026, 8, 1).date(),
    )
    start = datetime(2026, 7, 3, 0, 0, 0)
    end = datetime(2026, 8, 1, 23, 59, 59)
    validate_period_card_for_reservation(None, card, BillType.night, start, end, 1)
    try:
        validate_period_card_for_reservation(None, card, BillType.monthly, start, end, 1)
        raise AssertionError("上班族月卡不应走普通月卡预约")
    except ValueError as e:
        assert "夜读" in str(e)


def test_reservation_open_window_night_weekday():
    from app.models import Reservation
    from app.services.booking import reservation_open_window, reservation_unlock_allowed

    res = Reservation(
        user_id=1,
        seat_id=1,
        bill_type=BillType.night,
        pay_status=1,
        status=0,
        start_time=datetime(2026, 7, 6, 0, 0, 0),
        end_time=datetime(2026, 8, 4, 23, 59, 59),
    )
    assert reservation_open_window(res, datetime(2026, 7, 6, 10, 0, 0)) is not None
    assert not reservation_unlock_allowed(res, datetime(2026, 7, 6, 10, 0, 0))
    win = reservation_open_window(res, datetime(2026, 7, 6, 19, 0, 0))
    assert win is not None
    assert reservation_unlock_allowed(res, datetime(2026, 7, 6, 17, 45, 0))
    assert reservation_unlock_allowed(res, datetime(2026, 7, 6, 23, 30, 0))
    assert not reservation_unlock_allowed(res, datetime(2026, 7, 6, 23, 31, 0))


def test_reservation_open_window_night_weekend():
    from app.models import Reservation
    from app.services.booking import reservation_unlock_allowed

    res = Reservation(
        user_id=1,
        seat_id=1,
        bill_type=BillType.night,
        pay_status=1,
        status=0,
        start_time=datetime(2026, 7, 5, 0, 0, 0),
        end_time=datetime(2026, 8, 3, 23, 59, 59),
    )
    assert reservation_unlock_allowed(res, datetime(2026, 7, 5, 8, 0, 0))
    assert not reservation_unlock_allowed(res, datetime(2026, 7, 5, 7, 0, 0))


def test_reservation_open_window_store_hours():
    from app.models import Reservation
    from app.services.booking import reservation_unlock_allowed

    res = Reservation(
        user_id=1,
        seat_id=1,
        bill_type=BillType.hourly,
        pay_status=1,
        status=0,
        start_time=datetime(2026, 7, 6, 9, 0, 0),
        end_time=datetime(2026, 7, 6, 12, 0, 0),
    )
    assert reservation_unlock_allowed(res, datetime(2026, 7, 6, 8, 45, 0))
    assert not reservation_unlock_allowed(res, datetime(2026, 7, 6, 7, 0, 0))
    assert reservation_unlock_allowed(res, datetime(2026, 7, 6, 11, 0, 0))
    assert not reservation_unlock_allowed(res, datetime(2026, 7, 6, 12, 30, 0))


if __name__ == "__main__":
    test_session_multi_day_deduct()
    test_weekly_one_shot()
    test_quarterly_bill_type()
    test_hourly_single_use_must_match_remaining()
    test_hourly_50h_partial_use()
    test_daily_pass_three_day_continuous()
    test_office_night_monthly_period()
    test_office_night_rejects_over_30_days()
    test_legacy_monthly_office_card_uses_night_bill()
    test_reservation_open_window_night_weekday()
    test_reservation_open_window_night_weekend()
    test_reservation_open_window_store_hours()
    print("All card rule tests passed.")
