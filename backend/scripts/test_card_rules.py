"""期限卡核销规则单元测试（无需启动服务）。"""

from datetime import datetime, timedelta

from decimal import Decimal

from app.models import BillType, CardType, PeriodCard, RewardType
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


def test_weekly_consecutive_in_validity():
    """周卡：90 天效期内须预约连续 7 天。"""
    from datetime import date

    card = PeriodCard(
        user_id=1,
        card_name="周卡",
        card_type=CardType.weekly,
        status=1,
        start_date=date(2026, 7, 1),
        end_date=date(2026, 9, 28),
        total_sessions=7,
    )
    start = datetime(2026, 7, 5, 7, 30, 0)
    end = datetime(2026, 7, 11, 23, 30, 0)
    validate_period_card_for_reservation(None, card, BillType.weekly, start, end, 1)
    consume_period_card(None, card, BillType.weekly, start, end, 1)
    assert card.status == 0


def test_weekly_one_shot():
    from datetime import date

    card = PeriodCard(
        user_id=1,
        card_name="周卡",
        card_type=CardType.weekly,
        status=1,
        start_date=date(2026, 7, 1),
        end_date=date(2026, 9, 28),
        total_sessions=7,
    )
    start = datetime(2026, 7, 5, 7, 30, 0)
    end = datetime(2026, 7, 11, 23, 30, 0)
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


def test_three_day_pass_validity_window():
    """三天卡：15 天效期内须预约连续 3 天。"""
    from datetime import date

    from app.services.card_service import validity_days_for_reward

    assert validity_days_for_reward(RewardType.day_pass, 3) == 15
    today = date(2026, 7, 1)
    card = PeriodCard(
        user_id=1,
        card_name="三天卡",
        card_type=CardType.daily,
        status=1,
        start_date=today,
        end_date=today + timedelta(days=14),
        total_sessions=3,
    )
    start = datetime(2026, 7, 5, 7, 30, 0)
    end = datetime(2026, 7, 7, 23, 30, 0)
    validate_period_card_for_reservation(None, card, BillType.daily, start, end, 1)


def test_hourly_card_has_validity():
    from datetime import date

    card = PeriodCard(
        user_id=1,
        card_name="四小时",
        card_type=CardType.hourly,
        status=1,
        remaining_hours=Decimal("4"),
        total_hours=Decimal("4"),
        start_date=date(2026, 7, 1),
        end_date=date(2026, 9, 28),
    )
    start = datetime(2026, 7, 5, 9, 0, 0)
    end = datetime(2026, 7, 5, 12, 0, 0)
    validate_period_card_for_reservation(None, card, BillType.hourly, start, end, 1)


def test_monthly_consecutive_in_validity():
    """月卡：180 天效期内须预约连续 30 天。"""
    from datetime import date

    card = PeriodCard(
        user_id=1,
        card_name="通坐月卡",
        card_type=CardType.monthly,
        status=1,
        start_date=date(2026, 7, 1),
        end_date=date(2026, 12, 27),
        total_sessions=30,
    )
    start = datetime(2026, 7, 5, 7, 30, 0)
    end = datetime(2026, 8, 3, 23, 30, 0)
    validate_period_card_for_reservation(None, card, BillType.monthly, start, end, 1)
    consume_period_card(None, card, BillType.monthly, start, end, 1)
    assert card.status == 0


def test_monthly_use_window_allows_30_day_booking():
    """月卡效期内开始预约即可；30 天预约可超出卡面 end_date。"""
    from datetime import date

    card = PeriodCard(
        user_id=1,
        card_name="新客月卡",
        card_type=CardType.monthly,
        status=1,
        start_date=date(2026, 7, 1),
        end_date=date(2026, 12, 27),
        total_sessions=30,
    )
    start = datetime(2026, 7, 5, 7, 30, 0)
    end = datetime(2026, 8, 3, 23, 30, 0)
    validate_period_card_for_reservation(None, card, BillType.monthly, start, end, 1)
    consume_period_card(None, card, BillType.monthly, start, end, 1)
    assert card.status == 0


def test_hourly_one_shot_flexible_duration():
    """4 小时卡可约 3 小时，一次性核销整张卡。"""
    card = _card(CardType.hourly, remaining_hours=Decimal("4"), total_hours=Decimal("4"))
    start = datetime(2026, 6, 24, 9, 0, 0)
    end3 = datetime(2026, 6, 24, 12, 0, 0)
    assert not hourly_allows_partial_use(card)
    validate_period_card_for_reservation(None, card, BillType.hourly, start, end3, 1)
    consume_period_card(None, card, BillType.hourly, start, end3, 1)
    assert card.remaining_hours == Decimal("0")
    assert card.status == 0


def test_hourly_rejects_over_balance():
    card = _card(CardType.hourly, remaining_hours=Decimal("4"), total_hours=Decimal("4"))
    start = datetime(2026, 6, 24, 9, 0, 0)
    end5 = datetime(2026, 6, 24, 14, 0, 0)
    try:
        validate_period_card_for_reservation(None, card, BillType.hourly, start, end5, 1)
        raise AssertionError("不应允许超过余额的预约")
    except ValueError as e:
        assert "不能超过" in str(e) or "余额" in str(e)


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


def test_repair_misissued_monthly_validity():
    from datetime import date

    from app.services.card_service import repair_misissued_card_validity

    card = PeriodCard(
        user_id=1,
        card_name="通坐月卡",
        card_type=CardType.monthly,
        status=1,
        start_date=date(2026, 7, 1),
        end_date=date(2026, 7, 30),
        total_sessions=30,
    )
    assert repair_misissued_card_validity(card)
    assert card.end_date == date(2026, 12, 27)


def test_repair_misissued_summer_bimonthly_validity():
    """暑期双月卡误把连续 60 天当成效期时，纠正为 180 天。"""
    from datetime import date

    from app.services.card_service import repair_misissued_card_validity

    card = PeriodCard(
        user_id=1,
        card_name="暑期双月卡",
        card_type=CardType.monthly,
        status=1,
        start_date=date(2026, 7, 1),
        end_date=date(2026, 8, 29),
        total_sessions=60,
    )
    assert repair_misissued_card_validity(card)
    assert card.end_date == date(2026, 12, 27)


def test_summer_bimonthly_consecutive_in_180_day_validity():
    """暑期双月卡：180 天效期内须预约连续 60 天。"""
    from datetime import date

    card = PeriodCard(
        user_id=1,
        card_name="暑期双月卡",
        card_type=CardType.monthly,
        status=1,
        start_date=date(2026, 7, 1),
        end_date=date(2026, 12, 27),
        total_sessions=60,
    )
    start = datetime(2026, 7, 5, 7, 30, 0)
    end = datetime(2026, 9, 2, 23, 30, 0)
    validate_period_card_for_reservation(None, card, BillType.monthly, start, end, 1)
    consume_period_card(None, card, BillType.monthly, start, end, 1)
    assert card.status == 0


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


def test_office_night_rejects_under_30_days():
    card = PeriodCard(
        user_id=1,
        card_name="知行岛晚自习月卡",
        card_type=CardType.night_monthly,
        status=1,
        start_date=datetime(2026, 7, 3).date(),
        end_date=datetime(2026, 9, 1).date(),
        total_sessions=30,
    )
    start = datetime(2026, 7, 3, 0, 0, 0)
    end = datetime(2026, 7, 10, 23, 59, 59)
    try:
        validate_period_card_for_reservation(None, card, BillType.night, start, end, 1)
        raise AssertionError("不应少于30天")
    except ValueError as e:
        assert "30" in str(e)


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


def test_legacy_monthly_office_card_auto_upgraded():
    from app.models import PeriodCard
    from app.services.card_service import ensure_office_night_card_type, validate_period_card_for_reservation

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
    assert card.card_type == CardType.night_monthly
    assert card.daily_start is not None


def test_office_night_booking_at_midnight_not_blocked():
    """预约开始时间为 00:00 时不应触发 18:00 限制（时段仅在开门/入座时校验）。"""
    card = PeriodCard(
        user_id=1,
        card_name="「上班族」月卡",
        card_type=CardType.night_monthly,
        status=1,
        start_date=datetime(2026, 7, 3).date(),
        end_date=datetime(2026, 8, 1).date(),
        daily_start=datetime.strptime("18:00", "%H:%M").time(),
    )
    start = datetime(2026, 7, 3, 0, 0, 0)
    end = datetime(2026, 8, 1, 23, 59, 59)
    validate_period_card_for_reservation(None, card, BillType.night, start, end, 1)


def test_night_reservation_blocks_saturday_morning():
    from app.models import Reservation
    from app.services.business import reservation_blocks_interval

    night = Reservation(
        user_id=1,
        store_id=1,
        seat_id=21,
        bill_type=BillType.night,
        pay_status=1,
        status=0,
        start_time=datetime(2026, 7, 3, 0, 0, 0),
        end_time=datetime(2026, 8, 1, 23, 59, 59),
    )
    morning = datetime(2026, 7, 4, 9, 0, 0)
    noon = datetime(2026, 7, 4, 11, 0, 0)
    assert reservation_blocks_interval(night, morning, noon)


def test_night_reservation_does_not_block_morning():
    from app.models import Reservation
    from app.services.business import reservation_blocks_interval

    night = Reservation(
        user_id=1,
        store_id=1,
        seat_id=1,
        bill_type=BillType.night,
        pay_status=1,
        status=0,
        start_time=datetime(2026, 7, 3, 0, 0, 0),
        end_time=datetime(2026, 8, 1, 23, 59, 59),
    )
    morning_start = datetime(2026, 7, 3, 9, 0, 0)
    morning_end = datetime(2026, 7, 3, 12, 0, 0)
    assert not reservation_blocks_interval(night, morning_start, morning_end)


def test_night_reservation_blocks_evening():
    from app.models import Reservation
    from app.services.business import reservation_blocks_interval

    night = Reservation(
        user_id=1,
        store_id=1,
        seat_id=1,
        bill_type=BillType.night,
        pay_status=1,
        status=0,
        start_time=datetime(2026, 7, 3, 0, 0, 0),
        end_time=datetime(2026, 8, 1, 23, 59, 59),
    )
    evening_start = datetime(2026, 7, 3, 19, 0, 0)
    evening_end = datetime(2026, 7, 3, 21, 0, 0)
    assert reservation_blocks_interval(night, evening_start, evening_end)


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


def test_reservation_open_window_night_monthly_weekday():
    from app.models import Reservation
    from app.services.booking import reservation_unlock_allowed

    res = Reservation(
        user_id=1,
        seat_id=1,
        bill_type=BillType.night_monthly,
        pay_status=1,
        status=0,
        start_time=datetime(2026, 7, 6, 0, 0, 0),
        end_time=datetime(2026, 8, 4, 23, 59, 59),
    )
    assert not reservation_unlock_allowed(res, datetime(2026, 7, 6, 10, 0, 0))
    assert reservation_unlock_allowed(res, datetime(2026, 7, 6, 18, 0, 0))


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
    test_hourly_one_shot_flexible_duration()
    test_hourly_rejects_over_balance()
    test_hourly_50h_partial_use()
    test_daily_pass_three_day_continuous()
    test_office_night_monthly_period()
    test_office_night_rejects_under_30_days()
    test_office_night_rejects_over_30_days()
    test_legacy_monthly_office_card_uses_night_bill()
    test_legacy_monthly_office_card_auto_upgraded()
    test_office_night_booking_at_midnight_not_blocked()
    test_night_reservation_does_not_block_morning()
    test_night_reservation_blocks_saturday_morning()
    test_night_reservation_blocks_evening()
    test_reservation_open_window_night_weekday()
    test_reservation_open_window_night_weekend()
    test_reservation_open_window_store_hours()
    print("All card rule tests passed.")
