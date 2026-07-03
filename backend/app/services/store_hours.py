"""门店营业时间与夜读月卡时段（全项目统一引用）。"""

from datetime import date, datetime, time

# 门店营业时间（除夜读月卡外的预约/开门/按小时选时）
STORE_OPEN_START = time(7, 30)
STORE_OPEN_END = time(23, 30)
STORE_HOURS_LABEL = "7:30-23:30"

# 夜读/晚自习月卡：每日可入座、开门时段
OFFICE_NIGHT_WEEKDAY_START = time(18, 0)
OFFICE_NIGHT_WEEKDAY_END = time(23, 30)
OFFICE_NIGHT_WEEKEND_START = time(7, 30)
OFFICE_NIGHT_WEEKEND_END = time(23, 30)

OFFICE_NIGHT_USAGE_RULE = (
    "工作日 18:00-23:30 · 周六日 7:30-23:30 可入座"
    "（工作日白天座位可与他人分时共用）"
)
OFFICE_NIGHT_BOOKING_HINT = "选择开始使用日期即可，最长连续 30 天；每日具体时段在到店开门时校验"


def night_window_for_date(day: date) -> tuple[time, time, str]:
    """夜读月卡当日可开门/入座时段。"""
    if day.weekday() < 5:
        return OFFICE_NIGHT_WEEKDAY_START, OFFICE_NIGHT_WEEKDAY_END, "工作日"
    return OFFICE_NIGHT_WEEKEND_START, OFFICE_NIGHT_WEEKEND_END, "周六日"


def night_seat_block_window_for_date(day: date) -> tuple[time, time, str]:
    """夜读固定座位占用时段：与当日可入座时段一致（工作日仅晚间，周六日全天营业时段）。"""
    return night_window_for_date(day)


def _clock_to_minutes(clock: time) -> int:
    return clock.hour * 60 + clock.minute


def is_within_store_hours(clock: time) -> bool:
    cur = _clock_to_minutes(clock)
    return _clock_to_minutes(STORE_OPEN_START) <= cur <= _clock_to_minutes(STORE_OPEN_END)


def validate_store_time_range(start_time: datetime, end_time: datetime) -> None:
    """非夜读预约须在营业时间内。"""
    if end_time <= start_time:
        raise ValueError("结束时间须晚于开始时间")
    if start_time.date() != end_time.date():
        raise ValueError(f"单次预约须在当日 {STORE_HOURS_LABEL} 营业时段内")
    if not is_within_store_hours(start_time.time()):
        raise ValueError(f"开始时间须在营业时间 {STORE_HOURS_LABEL} 内")
    if not is_within_store_hours(end_time.time()):
        raise ValueError(f"结束时间须在营业时间 {STORE_HOURS_LABEL} 内")


def store_range_bounds(start_time: datetime, end_time: datetime) -> tuple[datetime, datetime]:
    """日期型预约：首日开门、末日打烊（7:30-23:30）。"""
    start = datetime.combine(start_time.date(), STORE_OPEN_START)
    end = datetime.combine(end_time.date(), STORE_OPEN_END)
    if end <= start:
        raise ValueError("结束日期不能早于开始日期")
    return start, end


def night_date_range_bounds(start_time: datetime, end_time: datetime) -> tuple[datetime, datetime]:
    """夜读月卡：按自然日存储，每日时段在开门时校验。"""
    start = start_time.replace(hour=0, minute=0, second=0, microsecond=0)
    end = end_time.replace(hour=23, minute=59, second=59, microsecond=0)
    if end <= start:
        raise ValueError("结束日期须晚于开始日期")
    return start, end
