import logging
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models import BillType, PeriodCard, PricingRule, Reservation, Seat, StudyStat, User, WalletLog
from app.services.points import add_points
from app.services.seat_setup import seat_code_to_slot
from app.services.business import find_seat_conflict, update_study_title

logger = logging.getLogger(__name__)


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
    conflict = find_seat_conflict(db, seat.id, start, end)
    if conflict:
        raise ValueError("该座位时段已被预约")
    return seat


def seat_conflict_excluding(
    db: Session,
    seat_id: int,
    start: datetime,
    end: datetime,
    exclude_reservation_id: int | None = None,
) -> Reservation | None:
    return find_seat_conflict(db, seat_id, start, end, exclude_reservation_id)


def change_reservation_seat(db: Session, reservation: Reservation, new_seat_id: int) -> tuple[Seat, Seat]:
    if reservation.status not in (0, 1):
        raise ValueError("当前订单状态不可换座")
    if reservation.pay_status != 1:
        raise ValueError("仅已付款订单可换座")
    if reservation.end_time <= datetime.now():
        raise ValueError("预约已结束，不可换座")

    old_seat = db.get(Seat, reservation.seat_id)
    if not old_seat:
        raise ValueError("原座位不存在")

    new_seat = db.get(Seat, new_seat_id)
    if not new_seat:
        raise ValueError("目标座位不存在")
    if new_seat.id == reservation.seat_id:
        raise ValueError("已是该座位，无需更换")
    if new_seat.store_id != reservation.store_id or new_seat.is_buffer or new_seat.status != 1:
        raise ValueError("目标座位不可用")

    conflict = seat_conflict_excluding(
        db,
        new_seat.id,
        reservation.start_time,
        reservation.end_time,
        exclude_reservation_id=reservation.id,
    )
    if conflict:
        raise ValueError(f"座位 {new_seat.seat_code} 在该时段已被占用")

    reservation.seat_id = new_seat.id
    return new_seat, old_seat


def seat_options_for_change(db: Session, reservation: Reservation) -> list[dict]:
    from app.models import Zone

    zones = {
        z.id: z.name
        for z in db.scalars(select(Zone).where(Zone.store_id == reservation.store_id)).all()
    }
    seats = sorted(
        db.scalars(
            select(Seat)
            .where(Seat.store_id == reservation.store_id, Seat.is_buffer == 0)
        ).all(),
        key=lambda s: seat_code_to_slot(s.seat_code) or 9999,
    )

    options: list[dict] = []
    for seat in seats:
        if seat.id == reservation.seat_id:
            options.append(
                {
                    "id": seat.id,
                    "seat_code": seat.seat_code,
                    "zone_name": zones.get(seat.zone_id, "-"),
                    "selectable": False,
                    "reason": "当前座位",
                }
            )
            continue
        if seat.status != 1:
            options.append(
                {
                    "id": seat.id,
                    "seat_code": seat.seat_code,
                    "zone_name": zones.get(seat.zone_id, "-"),
                    "selectable": False,
                    "reason": "座位已停用",
                }
            )
            continue
        conflict = seat_conflict_excluding(
            db,
            seat.id,
            reservation.start_time,
            reservation.end_time,
            exclude_reservation_id=reservation.id,
        )
        if conflict:
            options.append(
                {
                    "id": seat.id,
                    "seat_code": seat.seat_code,
                    "zone_name": zones.get(seat.zone_id, "-"),
                    "selectable": False,
                    "reason": "时段冲突",
                }
            )
        else:
            options.append(
                {
                    "id": seat.id,
                    "seat_code": seat.seat_code,
                    "zone_name": zones.get(seat.zone_id, "-"),
                    "selectable": True,
                    "reason": None,
                }
            )
    return options


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


def adjust_user_balance(
    db: Session, user: User, delta: Decimal, *, require_sufficient: bool = False
) -> bool:
    """原子调整用户余额（数据库行级更新，避免并发丢失更新/超扣）。

    require_sufficient 且为扣减时，余额不足则不扣减并返回 False。
    """
    if delta == 0:
        return True
    stmt = update(User).where(User.id == user.id)
    if require_sufficient and delta < 0:
        stmt = stmt.where(User.balance >= -delta)
    stmt = stmt.values(balance=User.balance + delta)
    result = db.execute(stmt)
    if result.rowcount != 1:
        return False
    db.refresh(user)
    return True


def add_wallet_log(
    db: Session,
    user: User,
    log_type: str,
    amount: Decimal,
    remark: str,
    ref_order: str | None = None,
) -> WalletLog:
    amount = Decimal(str(amount or 0))
    if log_type == "consume":
        delta = -amount
    elif log_type in ("recharge", "refund"):
        delta = amount
    else:
        delta = Decimal("0")
    if delta != 0:
        ok = adjust_user_balance(db, user, delta, require_sufficient=(log_type == "consume"))
        if not ok:
            raise ValueError("余额不足")
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


def fulfill_recharge_order(db: Session, order) -> bool:
    """履约充值订单：余额入账并记流水。幂等——已支付订单不会重复入账。"""
    if order is None or order.pay_status == 1:
        return False
    user = db.get(User, order.user_id)
    if not user:
        return False
    order.pay_status = 1
    order.paid_at = datetime.now()
    add_wallet_log(db, user, "recharge", order.amount, "余额充值", order.order_no)
    return True


EARLY_CHECKIN_MINUTES = 15
STORE_OPEN_START = time(7, 30)
STORE_OPEN_END = time(23, 30)


def reservation_open_window(
    reservation: Reservation,
    now: datetime | None = None,
) -> tuple[datetime, datetime] | None:
    """当日允许开门/入座的时间窗（营业时间与预约时段的交集）。"""
    from app.services.card_service import night_window_for_date

    now = now or datetime.now()
    today = now.date()
    res_start = reservation.start_time
    res_end = reservation.end_time

    if today < res_start.date() or today > res_end.date():
        return None

    if reservation.bill_type == BillType.night:
        win_start, win_end, _ = night_window_for_date(today)
    else:
        win_start, win_end = STORE_OPEN_START, STORE_OPEN_END

    day_open = datetime.combine(today, win_start) - timedelta(minutes=EARLY_CHECKIN_MINUTES)
    day_close = datetime.combine(today, win_end)

    if res_start.date() == res_end.date() == today:
        open_from = max(day_open, res_start - timedelta(minutes=EARLY_CHECKIN_MINUTES))
        open_until = min(day_close, res_end)
    elif res_start.date() == today:
        open_from = max(day_open, res_start - timedelta(minutes=EARLY_CHECKIN_MINUTES))
        open_until = day_close
    elif res_end.date() == today:
        open_from = day_open
        open_until = min(day_close, res_end)
    else:
        open_from = day_open
        open_until = day_close

    if open_until <= open_from:
        return None
    return open_from, open_until


def reservation_unlock_message(reservation: Reservation, now: datetime | None = None) -> str:
    """无法开门时的提示文案。"""
    from app.services.card_service import night_window_for_date

    now = now or datetime.now()
    if reservation.pay_status != 1:
        return "订单未支付"
    if reservation.status == 3:
        return "订单已取消"
    if reservation.status == 2:
        return "订单已结束"
    if now.date() < reservation.start_time.date():
        return f"{reservation.start_time.strftime('%m月%d日')} 起可开门"
    if now.date() > reservation.end_time.date():
        return "订单已结束，无法开门"

    window = reservation_open_window(reservation, now)
    if window and window[0] <= now <= window[1]:
        return ""

    today = now.date()
    if reservation.bill_type == BillType.night:
        win_start, win_end, label = night_window_for_date(today)
        return (
            f"{label}夜读时段 {win_start.strftime('%H:%M')}-{win_end.strftime('%H:%M')} 可开门"
            f"（可提前 {EARLY_CHECKIN_MINUTES} 分钟）"
        )
    return (
        f"营业时间 {STORE_OPEN_START.strftime('%H:%M')}-{STORE_OPEN_END.strftime('%H:%M')} 可开门"
        f"（可提前 {EARLY_CHECKIN_MINUTES} 分钟）"
    )


def reservation_unlock_allowed(
    reservation: Reservation,
    now: datetime | None = None,
) -> bool:
    """是否在允许开门/入座的时间窗内。"""
    now = now or datetime.now()
    if reservation.pay_status != 1:
        return False
    if reservation.status == 3:
        return False
    if reservation.status == 2:
        return False
    window = reservation_open_window(reservation, now)
    if not window:
        return False
    return window[0] <= now <= window[1]


def finalize_expired_reservation(
    db: Session,
    reservation: Reservation,
    now: datetime | None = None,
) -> bool:
    """预约时段结束后自动完结（未入座视为取消，已入座视为完成）。"""
    now = now or datetime.now()
    if reservation.status not in (0, 1):
        return False
    if reservation.end_time > now:
        return False
    if reservation.status == 1:
        reservation.status = 2
        reservation.actual_end_time = reservation.end_time
        user = db.get(User, reservation.user_id)
        if user:
            record_study_on_checkout(db, reservation, user)
    else:
        reservation.status = 3
    return True


def _fmt_status_time(dt: datetime) -> str:
    return dt.strftime("%m月%d日 %H:%M")


def auto_checkin_reservation(
    db: Session,
    reservation: Reservation,
    *,
    when: datetime | None = None,
) -> bool:
    """预约时段内自动入座，无需用户手动签到。"""
    when = when or datetime.now()
    if reservation.pay_status != 1 or reservation.status != 0:
        return False
    window = reservation_open_window(reservation, when)
    if not window or not (window[0] <= when <= window[1]):
        return False
    reservation.status = 1
    reservation.check_in_time = when
    return True


def auto_checkin_due_batch(db: Session) -> int:
    now = datetime.now()
    rows = db.scalars(
        select(Reservation).where(
            Reservation.pay_status == 1,
            Reservation.status == 0,
            Reservation.end_time > now,
        )
    ).all()
    count = 0
    for row in rows:
        if auto_checkin_reservation(db, row, when=now):
            count += 1
    if count:
        db.commit()
    return count


def reservation_status_display(
    reservation: Reservation,
    now: datetime | None = None,
) -> tuple[str, str | None]:
    now = now or datetime.now()
    if reservation.pay_status != 1:
        return "待支付", "请完成支付后使用"
    if reservation.status == 3:
        return "已取消", None
    if reservation.status == 2:
        hint = None
        if reservation.actual_end_time:
            hint = f"结束于 {_fmt_status_time(reservation.actual_end_time)}"
        return "已完成", hint
    if reservation.status == 1:
        if reservation.check_in_time:
            return "使用中", f"自 {_fmt_status_time(reservation.check_in_time)} 起"
        return "使用中", "可到店开门或直接入座"
    early = reservation.start_time - timedelta(minutes=EARLY_CHECKIN_MINUTES)
    if now < early:
        return "已预约", f"{_fmt_status_time(reservation.start_time)} 起可到店"
    if now <= reservation.end_time:
        return "已预约", "到达时段后自动开始，到店开门即可"
    return "已结束", "预约时段已结束"


async def finalize_reservation_after_pay(db: Session, reservation: Reservation) -> None:
    from app.services.business import create_ble_keys_for_reservation

    await create_ble_keys_for_reservation(db, reservation)
    auto_checkin_reservation(db, reservation)
    db.commit()
