from datetime import date, datetime, time, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import BillType, PeriodCard, PricingRule, Reservation, Seat, StudyStat, User, WalletLog
from app.services.points import add_points
from app.services.business import _seat_conflict_query, update_study_title


def resolve_booking_window(
    bill_type: BillType,
    start_time: datetime,
    end_time: datetime | None,
    rule: PricingRule | None = None,
) -> tuple[datetime, datetime]:
    """根据计费类型计算预约起止时间。"""
    if bill_type == BillType.hourly:
        if not end_time:
            raise ValueError("按小时预约需要结束时间")
        return start_time, end_time

    if bill_type == BillType.daily:
        day_start = start_time.replace(hour=0, minute=0, second=0, microsecond=0)
        if end_time and end_time > day_start:
            return day_start, end_time.replace(hour=23, minute=59, second=59)
        return day_start, day_start + timedelta(days=1)

    if bill_type == BillType.monthly:
        day_start = start_time.replace(hour=0, minute=0, second=0, microsecond=0)
        if end_time:
            day_end = end_time.replace(hour=23, minute=59, second=59, microsecond=0)
            if day_end <= day_start:
                raise ValueError("结束日期须晚于开始日期")
            return day_start, day_end
        days = rule.valid_days if rule and rule.valid_days else 30
        return day_start, (day_start + timedelta(days=days)).replace(
            hour=23, minute=59, second=59
        )

    if bill_type == BillType.weekly:
        day_start = start_time.replace(hour=0, minute=0, second=0, microsecond=0)
        if end_time:
            day_end = end_time.replace(hour=23, minute=59, second=59, microsecond=0)
            if day_end <= day_start:
                raise ValueError("结束日期须晚于开始日期")
            return day_start, day_end
        days = rule.valid_days if rule and rule.valid_days else 7
        return day_start, (day_start + timedelta(days=days - 1)).replace(
            hour=23, minute=59, second=59
        )

    if bill_type == BillType.quarterly:
        day_start = start_time.replace(hour=0, minute=0, second=0, microsecond=0)
        if end_time:
            day_end = end_time.replace(hour=23, minute=59, second=59, microsecond=0)
            if day_end <= day_start:
                raise ValueError("结束日期须晚于开始日期")
            return day_start, day_end
        days = rule.valid_days if rule and rule.valid_days else 90
        return day_start, (day_start + timedelta(days=days - 1)).replace(
            hour=23, minute=59, second=59
        )

    if bill_type == BillType.session:
        day_start = start_time.replace(hour=0, minute=0, second=0, microsecond=0)
        if end_time:
            day_end = end_time.replace(hour=23, minute=59, second=59, microsecond=0)
            if day_end < day_start:
                raise ValueError("结束日期不能早于开始日期")
            days = (day_end.date() - day_start.date()).days + 1
            if days > 30:
                raise ValueError("次卡单次最多连续预约30天")
            return day_start, day_end
        return day_start, day_start.replace(hour=23, minute=59, second=59)

    if bill_type == BillType.night:
        night_start = rule.night_start if rule and rule.night_start else time(18, 0)
        night_end = rule.night_end if rule and rule.night_end else time(0, 0)
        if end_time:
            if end_time <= start_time:
                raise ValueError("结束时间须晚于开始时间")
            return start_time, end_time
        base = start_time.replace(
            hour=night_start.hour, minute=night_start.minute, second=0, microsecond=0
        )
        if night_end.hour == 0 and night_end.minute == 0:
            end = base + timedelta(days=1)
        else:
            end = base.replace(hour=night_end.hour, minute=night_end.minute)
            if end <= base:
                end += timedelta(days=1)
        return base, end

    if bill_type == BillType.night_monthly:
        day_start = start_time.replace(hour=0, minute=0, second=0, microsecond=0)
        days = rule.valid_days if rule and rule.valid_days else 30
        night_start = rule.night_start if rule and rule.night_start else time(18, 0)
        start = day_start.replace(hour=night_start.hour, minute=night_start.minute)
        return start, day_start + timedelta(days=days)

    if end_time:
        return start_time, end_time
    return start_time, start_time + timedelta(hours=2)


def validate_seat_for_booking(db: Session, seat: Seat | None, store_id: int, start: datetime, end: datetime) -> Seat:
    if not seat:
        raise ValueError("请选择座位")
    if seat.store_id != store_id or seat.is_buffer or seat.status != 1:
        raise ValueError("座位不可用")
    conflict = db.scalar(_seat_conflict_query(seat.id, start, end))
    if conflict:
        raise ValueError("该座位时段已被预约")
    return seat


def record_study_on_checkout(db: Session, reservation: Reservation, user: User) -> None:
    check_in = reservation.check_in_time or reservation.start_time
    end = reservation.actual_end_time or datetime.now()
    minutes = max(int((end - check_in).total_seconds() / 60), 0)
    if minutes <= 0:
        return

    stat_date = check_in.date()
    stat = db.scalar(
        select(StudyStat).where(
            StudyStat.user_id == user.id,
            StudyStat.store_id == reservation.store_id,
            StudyStat.stat_date == stat_date,
        )
    )
    if stat:
        stat.total_minutes += minutes
        stat.session_count += 1
    else:
        db.add(
            StudyStat(
                user_id=user.id,
                store_id=reservation.store_id,
                stat_date=stat_date,
                total_minutes=minutes,
                session_count=1,
            )
        )

    total = db.scalar(
        select(func.coalesce(func.sum(StudyStat.total_minutes), 0)).where(StudyStat.user_id == user.id)
    ) or 0
    update_study_title(user, int(total))

    # 学习积分：每满 10 分钟 1 分，至少 1 分
    earned = max(minutes // 10, 1 if minutes >= 1 else 0)
    if earned > 0:
        add_points(
            db,
            user,
            earned,
            "study",
            f"自习 {minutes} 分钟",
            reservation.order_no,
        )


def add_wallet_log(
    db: Session,
    user: User,
    log_type: str,
    amount: Decimal,
    remark: str,
    ref_order: str | None = None,
) -> WalletLog:
    if log_type == "recharge":
        user.balance += amount
    elif log_type == "consume":
        user.balance -= amount
    elif log_type == "refund":
        user.balance += amount
    log = WalletLog(
        user_id=user.id,
        type=log_type,
        amount=amount,
        balance_after=user.balance,
        remark=remark,
        ref_order=ref_order,
    )
    db.add(log)
    return log
