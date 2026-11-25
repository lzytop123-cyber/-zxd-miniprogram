import logging
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models import (
    BillType,
    CardSource,
    CardType,
    PayType,
    PeriodCard,
    PricingRule,
    Reservation,
    Seat,
    StudyStat,
    User,
    WalletLog,
    Zone,
)
from app.services.business import find_seat_conflict, update_study_title
from app.services.seat_setup import seat_code_to_slot
from app.services.points import add_points
from app.services.store_hours import (
    STORE_HOURS_LABEL,
    STORE_OPEN_END,
    STORE_OPEN_START,
    night_date_range_bounds,
    night_window_for_date,
    store_range_bounds,
    validate_store_time_range,
)

logger = logging.getLogger(__name__)

# 未配置后台时的默认值；实际以 site_booking_settings.start_max_advance_days 为准
BOOKING_START_MAX_ADVANCE_DAYS_DEFAULT = 3
BOOKING_START_MAX_ADVANCE_DAYS_MIN = 0
BOOKING_START_MAX_ADVANCE_DAYS_MAX = 365


def clamp_booking_start_max_advance_days(days: int) -> int:
    return max(
        BOOKING_START_MAX_ADVANCE_DAYS_MIN,
        min(BOOKING_START_MAX_ADVANCE_DAYS_MAX, int(days)),
    )


def get_booking_start_max_advance_days(db: Session | None = None) -> int:
    """读取后台配置的「开始日最多提前天数」。"""
    if db is None:
        return BOOKING_START_MAX_ADVANCE_DAYS_DEFAULT
    try:
        from app.models import SiteBookingSetting

        row = db.get(SiteBookingSetting, 1)
        if row and row.start_max_advance_days is not None:
            return clamp_booking_start_max_advance_days(row.start_max_advance_days)
    except Exception:
        pass
    return BOOKING_START_MAX_ADVANCE_DAYS_DEFAULT


def validate_booking_start_advance(
    start: datetime,
    max_advance_days: int | None = None,
    today: date | None = None,
) -> None:
    """开始日须在今天起 max_advance_days 天内（含今天）。"""
    days = BOOKING_START_MAX_ADVANCE_DAYS_DEFAULT if max_advance_days is None else max_advance_days
    days = clamp_booking_start_max_advance_days(days)
    today = today or date.today()
    start_day = start.date()
    latest = today + timedelta(days=days)
    if start_day > latest:
        raise ValueError(f"为公平占座，最多提前{days}天开始预约")


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
        validate_store_time_range(start_time, end_time)
        return start_time, end_time

    if bill_type == BillType.daily:
        if not end_time:
            return store_range_bounds(start_time, start_time)
        if start_time.date() == end_time.date():
            validate_store_time_range(start_time, end_time)
            return start_time, end_time
        return store_range_bounds(start_time, end_time)

    if bill_type == BillType.monthly:
        if end_time:
            start, end = store_range_bounds(start_time, end_time)
            if end <= start:
                raise ValueError("结束日期须晚于开始日期")
            return start, end
        days = rule.valid_days if rule and rule.valid_days else 30
        end_day = start_time.date() + timedelta(days=days - 1)
        return store_range_bounds(start_time, datetime.combine(end_day, STORE_OPEN_END))

    if bill_type == BillType.weekly:
        if end_time:
            start, end = store_range_bounds(start_time, end_time)
            if end <= start:
                raise ValueError("结束日期须晚于开始日期")
            return start, end
        days = rule.valid_days if rule and rule.valid_days else 7
        end_day = start_time.date() + timedelta(days=days - 1)
        return store_range_bounds(start_time, datetime.combine(end_day, STORE_OPEN_END))

    if bill_type == BillType.quarterly:
        if end_time:
            start, end = store_range_bounds(start_time, end_time)
            if end <= start:
                raise ValueError("结束日期须晚于开始日期")
            return start, end
        days = rule.valid_days if rule and rule.valid_days else 90
        end_day = start_time.date() + timedelta(days=days - 1)
        return store_range_bounds(start_time, datetime.combine(end_day, STORE_OPEN_END))

    if bill_type == BillType.session:
        if end_time:
            days = (end_time.date() - start_time.date()).days + 1
            if days > 30:
                raise ValueError("次卡单次最多连续预约30天")
            return store_range_bounds(start_time, end_time)
        return store_range_bounds(start_time, start_time)

    if bill_type == BillType.night:
        if end_time:
            return night_date_range_bounds(start_time, end_time)
        night_start = rule.night_start if rule and rule.night_start else time(18, 0)
        night_end = rule.night_end if rule and rule.night_end else time(0, 0)
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
    from app.models import Store
    from app.services.store_seat_maps import SeatMapError, assert_seat_bookable

    if not seat:
        raise ValueError("请选择座位")
    store = db.get(Store, store_id)
    if not store:
        raise ValueError("门店不存在")
    try:
        assert_seat_bookable(db, store, seat)
    except SeatMapError as e:
        raise ValueError(str(e)) from e
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


def _assert_reservation_can_change_seat(reservation: Reservation) -> None:
    if reservation.status not in (0, 1):
        raise ValueError("当前订单状态不可换座")
    if reservation.pay_status != 1:
        raise ValueError("仅已付款订单可换座")
    if reservation.end_time <= datetime.now():
        raise ValueError("预约已结束，不可换座")


def change_reservation_seat(db: Session, reservation: Reservation, new_seat_id: int) -> tuple[Seat, Seat]:
    _assert_reservation_can_change_seat(reservation)

    old_seat = db.get(Seat, reservation.seat_id)
    if not old_seat:
        raise ValueError("原座位不存在")

    new_seat = db.get(Seat, new_seat_id)
    if not new_seat:
        raise ValueError("目标座位不存在")
    if new_seat.id == reservation.seat_id:
        raise ValueError("已是该座位，无需更换")
    from app.models import Store
    from app.services.store_seat_maps import SeatMapError, assert_seat_bookable

    store = db.get(Store, reservation.store_id)
    if not store:
        raise ValueError("门店不存在")
    try:
        assert_seat_bookable(db, store, new_seat)
    except SeatMapError as e:
        raise ValueError(str(e)) from e

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


def _occupant_brief(db: Session, row: Reservation) -> dict:
    user = db.get(User, row.user_id)
    end_label = row.end_time.strftime("%m-%d %H:%M") if row.end_time else ""
    nickname = (user.nickname if user else None) or "同学"
    return {
        "reservation_id": row.id,
        "user_id": row.user_id,
        "nickname": nickname,
        "end_time": row.end_time.isoformat(sep=" ", timespec="minutes") if row.end_time else None,
        "end_label": end_label,
        "label": f"{nickname} · ID {row.user_id} · 用到 {end_label}",
    }


def can_swap_reservations(
    db: Session, left: Reservation, right: Reservation, *, force: bool = False
) -> bool:
    try:
        _assert_reservation_can_change_seat(left)
        _assert_reservation_can_change_seat(right)
    except ValueError:
        return False
    if left.id == right.id or left.store_id != right.store_id or left.seat_id == right.seat_id:
        return False
    if force:
        return True
    if seat_conflict_excluding(db, right.seat_id, left.start_time, left.end_time, right.id):
        return False
    if seat_conflict_excluding(db, left.seat_id, right.start_time, right.end_time, left.id):
        return False
    return True


def swap_reservation_seats(
    db: Session,
    reservation_a: Reservation,
    reservation_b: Reservation,
    *,
    force: bool = False,
) -> tuple[Seat, Seat]:
    _assert_reservation_can_change_seat(reservation_a)
    _assert_reservation_can_change_seat(reservation_b)
    if reservation_a.id == reservation_b.id:
        raise ValueError("请选择另一笔订单对调")
    if reservation_a.store_id != reservation_b.store_id:
        raise ValueError("只能对调同一门店的订单")
    if reservation_a.seat_id == reservation_b.seat_id:
        raise ValueError("两单已是同一座位")

    seat_a = db.get(Seat, reservation_a.seat_id)
    seat_b = db.get(Seat, reservation_b.seat_id)
    if not seat_a or not seat_b:
        raise ValueError("座位不存在")
    if not force:
        if seat_conflict_excluding(db, seat_b.id, reservation_a.start_time, reservation_a.end_time, reservation_b.id):
            raise ValueError(f"座位 {seat_b.seat_code} 在本单时段还有其他人")
        if seat_conflict_excluding(db, seat_a.id, reservation_b.start_time, reservation_b.end_time, reservation_a.id):
            raise ValueError(f"座位 {seat_a.seat_code} 在对方时段还有其他人")

    reservation_a.seat_id, reservation_b.seat_id = seat_b.id, seat_a.id
    return seat_a, seat_b


def seat_options_for_change(db: Session, reservation: Reservation, *, for_admin: bool = False) -> list[dict]:
    from app.models import Store, Zone
    from app.services.seat_setup import seat_code_to_slot, zone_name_by_slot
    from app.services.store_seat_maps import is_image_mode, published_image_seat_ids

    store = db.get(Store, reservation.store_id)
    image_mode = is_image_mode(store)
    allowed_ids = published_image_seat_ids(db, reservation.store_id) if image_mode else None
    zone_names = {
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

    from app.services.business import reservation_blocks_interval

    eligible_seats: list[Seat] = []
    expected_codes_set: set[str] | None = None
    if not image_mode:
        from app.services.seat_setup import expected_seat_codes
        expected_codes_set = set(expected_seat_codes())

    for seat in seats:
        if image_mode:
            if allowed_ids is not None and seat.id not in allowed_ids and seat.id != reservation.seat_id:
                continue
        else:
            if expected_codes_set is not None and seat.seat_code not in expected_codes_set and seat.id != reservation.seat_id:
                continue
        eligible_seats.append(seat)

    check_ids = [
        s.id for s in eligible_seats if s.id != reservation.seat_id and s.status == 1
    ]
    conflict_by_seat: dict[int, Reservation] = {}
    if check_ids:
        now_dt = datetime.now()
        cand_rows = db.scalars(
            select(Reservation).where(
                Reservation.seat_id.in_(check_ids),
                Reservation.status.in_([0, 1]),
                Reservation.pay_status == 1,
                Reservation.end_time > now_dt,
                Reservation.start_time < reservation.end_time,
                Reservation.end_time > reservation.start_time,
                Reservation.id != reservation.id,
            )
        ).all()
        for cand in cand_rows:
            if cand.seat_id in conflict_by_seat:
                continue
            if reservation_blocks_interval(cand, reservation.start_time, reservation.end_time):
                conflict_by_seat[cand.seat_id] = cand

    options: list[dict] = []
    for seat in eligible_seats:
        if image_mode:
            zone_name = zone_names.get(seat.zone_id) or "-"
        else:
            zone_name = zone_name_by_slot(seat_code_to_slot(seat.seat_code)) or zone_names.get(seat.zone_id) or "-"
        base = {
            "id": seat.id,
            "seat_code": seat.seat_code,
            "zone_name": zone_name,
            "pos_x": seat.pos_x,
            "pos_y": seat.pos_y,
            "selectable": False,
            "can_swap": False,
            "occupied_by": None,
            "reason": None,
        }
        if seat.id == reservation.seat_id:
            base["reason"] = "当前座位"
            options.append(base)
            continue
        if seat.status != 1:
            base["reason"] = "座位已停用"
            options.append(base)
            continue
        conflict = conflict_by_seat.get(seat.id)
        if conflict:
            if for_admin:
                occupant = _occupant_brief(db, conflict)
                base["occupied_by"] = occupant
                base["can_swap"] = can_swap_reservations(db, reservation, conflict, force=True)
                base["reason"] = occupant["label"]
            else:
                base["reason"] = "时段冲突"
            options.append(base)
        else:
            base["selectable"] = True
            options.append(base)
        if for_admin and base["can_swap"]:
            base["selectable"] = True

    def _rank(item: dict) -> tuple[int, int]:
        slot = seat_code_to_slot(item["seat_code"]) or 9999
        if item.get("reason") == "当前座位":
            return (0, slot)
        if item.get("selectable") and not item.get("can_swap"):
            return (1, slot)
        if item.get("can_swap"):
            return (2, slot)
        return (3, slot)

    options.sort(key=_rank)
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


def fulfill_recharge_order(db: Session, order, *, success_time: str | None = None) -> bool:
    """履约充值订单：余额入账并记流水。幂等——已支付订单不会重复入账。"""
    if order is None or order.pay_status == 1:
        return False
    user = db.get(User, order.user_id)
    if not user:
        return False
    order.pay_status = 1
    from app.services.receipts import payment_time
    order.paid_at = payment_time(success_time)
    add_wallet_log(db, user, "recharge", order.amount, "余额充值", order.order_no)
    return True


EARLY_CHECKIN_MINUTES = 15
LATE_EXIT_MINUTES = 15


def reservation_open_window(
    reservation: Reservation,
    now: datetime | None = None,
) -> tuple[datetime, datetime] | None:
    """当日允许开门/入座的时间窗（营业时间与预约时段的交集，含提前入座与离场宽限）。"""
    now = now or datetime.now()
    today = now.date()
    res_start = reservation.start_time
    res_end = reservation.end_time
    res_end_grace = res_end + timedelta(minutes=LATE_EXIT_MINUTES)

    if today < res_start.date() or today > res_end.date():
        return None

    if reservation.bill_type in (BillType.night, BillType.night_monthly):
        win_start, win_end, _ = night_window_for_date(today)
    else:
        win_start, win_end = STORE_OPEN_START, STORE_OPEN_END

    day_open = datetime.combine(today, win_start) - timedelta(minutes=EARLY_CHECKIN_MINUTES)
    day_close = datetime.combine(today, win_end)

    if res_start.date() == res_end.date() == today:
        open_from = max(day_open, res_start - timedelta(minutes=EARLY_CHECKIN_MINUTES))
        open_until = min(day_close, res_end_grace)
    elif res_start.date() == today:
        open_from = max(day_open, res_start - timedelta(minutes=EARLY_CHECKIN_MINUTES))
        open_until = day_close
    elif res_end.date() == today:
        open_from = day_open
        open_until = min(day_close, res_end_grace)
    else:
        open_from = day_open
        open_until = day_close

    if open_until <= open_from:
        return None
    return open_from, open_until


def reservation_unlock_message(reservation: Reservation, now: datetime | None = None) -> str:
    """无法开门时的提示文案。"""
    now = now or datetime.now()
    if reservation.pay_status != 1:
        return "订单未支付"
    if reservation.status == 3:
        return "订单已取消"
    if reservation.status == 2:
        return "订单已结束"
    if now.date() < reservation.start_time.date():
        return f"{reservation.start_time.strftime('%m月%d日')} 起可开门"
    if now > reservation.end_time + timedelta(minutes=LATE_EXIT_MINUTES):
        return "订单已结束"

    window = reservation_open_window(reservation, now)
    if window:
        if window[0] <= now <= window[1]:
            return ""
        return f"{window[0].strftime('%H:%M')}-{window[1].strftime('%H:%M')} 可开门"

    today = now.date()
    if reservation.bill_type in (BillType.night, BillType.night_monthly):
        win_start, win_end, _label = night_window_for_date(today)
        return f"{win_start.strftime('%H:%M')}-{win_end.strftime('%H:%M')} 可开门"
    return f"{STORE_OPEN_START.strftime('%H:%M')}-{STORE_OPEN_END.strftime('%H:%M')} 可开门"


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
    db.refresh(reservation, with_for_update=True)
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
        try:
            from app.services.subscribe_notify import send_checkout_notify

            send_checkout_notify(db, reservation)
        except Exception:
            logger.warning("checkout notify error res=%s", reservation.id, exc_info=True)
    else:
        reservation.status = 3
        if reservation.pay_status == 0 and reservation.paid_at is None:
            from app.services.coupon_service import refund_coupon_for_reservation
            refund_coupon_for_reservation(db, reservation)
    return True


def _fmt_status_time(dt: datetime) -> str:
    return dt.strftime("%m月%d日 %H:%M")


def auto_checkin_reservation(
    db: Session,
    reservation: Reservation,
    *,
    when: datetime | None = None,
    allow_early: bool = False,
) -> bool:
    """预约时段内自动入座，无需用户手动签到（默认仅在开始时间到达后自动入座）。"""
    when = when or datetime.now()
    if reservation.pay_status != 1 or reservation.status != 0:
        return False
    if not allow_early and when < reservation.start_time:
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


BILL_TYPE_LABELS = {
    BillType.hourly: "按小时",
    BillType.daily: "天卡",
    BillType.weekly: "周卡",
    BillType.monthly: "月卡",
    BillType.quarterly: "季卡",
    BillType.night: "夜读票",
    BillType.night_monthly: "夜读月卡",
    BillType.session: "次卡",
}

CARD_TYPE_LABELS = {
    CardType.hourly: "小时卡",
    CardType.daily: "天卡",
    CardType.weekly: "周卡",
    CardType.monthly: "月卡",
    CardType.quarterly: "季卡",
    CardType.night_monthly: "夜读月卡",
    CardType.session: "次卡",
}

CARD_SOURCE_LABELS = {
    CardSource.meituan: "美团/点评团购",
    CardSource.douyin: "抖音团购",
    CardSource.purchase: "微信购卡",
    CardSource.admin: "门店发放",
    CardSource.gift: "赠送",
}


def reservation_display_meta(
    db: Session,
    reservation: Reservation,
    *,
    seat: Seat | None = None,
    zones_map: dict[int, Zone] | None = None,
    cards_map: dict[int, PeriodCard] | None = None,
) -> dict:
    """订单列表展示：套餐类型、用卡、支付来源、座位区域。"""
    bill_label = BILL_TYPE_LABELS.get(reservation.bill_type, reservation.bill_type.value)

    seat_obj = seat if seat is not None else db.get(Seat, reservation.seat_id)
    zone_name = None
    if seat_obj:
        from app.services.seat_setup import seat_code_to_slot, zone_name_by_slot

        zone_name = zone_name_by_slot(seat_code_to_slot(seat_obj.seat_code))
        if not zone_name and seat_obj.zone_id:
            zone = (
                zones_map.get(seat_obj.zone_id)
                if zones_map is not None
                else db.get(Zone, seat_obj.zone_id)
            )
            zone_name = zone.name if zone else None

    card_name = None
    card_type_label = None
    pay_source_label = None
    usage_label = bill_label

    if reservation.pay_status != 1:
        pay_source_label = "待支付"
    elif reservation.pay_type == PayType.admin:
        pay_source_label = "前台收款"
    elif reservation.pay_type == PayType.wechat:
        pay_source_label = "微信支付"
    elif reservation.pay_type == PayType.balance:
        pay_source_label = "余额支付"
    elif reservation.pay_type == PayType.period_card or reservation.period_card_id:
        if reservation.period_card_id:
            card = (
                cards_map.get(reservation.period_card_id)
                if cards_map is not None
                else db.get(PeriodCard, reservation.period_card_id)
            )
        else:
            card = None
        if card:
            card_name = card.card_name
            card_type_label = CARD_TYPE_LABELS.get(card.card_type, "期限卡")
            pay_source_label = CARD_SOURCE_LABELS.get(card.source, "期限卡")
            usage_label = card_type_label
            if card_name and card_name != card_type_label:
                usage_label = f"{card_type_label} · {card_name}"
        else:
            pay_source_label = "期限卡"
    elif (reservation.final_price or Decimal("0")) > 0:
        pay_source_label = "微信支付"
    else:
        pay_source_label = "期限卡抵扣"

    return {
        "zone_name": zone_name,
        "bill_type_label": bill_label,
        "usage_label": usage_label,
        "card_name": card_name,
        "card_type_label": card_type_label,
        "pay_source_label": pay_source_label,
        "pay_type": reservation.pay_type.value if reservation.pay_type else None,
    }


def reservation_status_display(
    reservation: Reservation,
    now: datetime | None = None,
) -> tuple[str, str | None]:
    now = now or datetime.now()
    if reservation.status == 3:
        if reservation.pay_status == 2:
            return "已退款", None
        if reservation.pay_status == 0 and reservation.paid_at:
            return "退款待确认", reservation.refund_remark
        return "已取消", None
    if reservation.pay_status != 1:
        return "待支付", "请完成支付后使用"
    if reservation.status == 2:
        hint = None
        if reservation.actual_end_time:
            hint = f"结束于 {_fmt_status_time(reservation.actual_end_time)}"
        return "已完成", hint
    if reservation.status == 1:
        if now > reservation.end_time:
            end_at = reservation.actual_end_time or reservation.end_time
            return "已完成", f"结束于 {_fmt_status_time(end_at)}"
        if reservation.check_in_time:
            return "使用中", f"自 {_fmt_status_time(reservation.check_in_time)} 起"
        return "使用中", "可到店开门或直接入座"
    early = reservation.start_time - timedelta(minutes=EARLY_CHECKIN_MINUTES)
    if now < early:
        return "已预约", f"{_fmt_status_time(reservation.start_time)} 起可到店"
    if now <= reservation.end_time:
        return "已预约", "到达时段后自动开始，到店开门即可"
    return "已结束", "预约时段已结束"


def calc_extend_price(
    db: Session,
    reservation: Reservation,
    extra_hours: int,
) -> Decimal:
    """计算在线续时费用：优先按门店按小时定价规则，否则按原订单均价估算。"""
    seat = db.get(Seat, reservation.seat_id)
    seat_type = (seat.seat_type if seat and seat.seat_type else "standard")
    rule = db.scalar(
        select(PricingRule).where(
            PricingRule.store_id == reservation.store_id,
            PricingRule.bill_type == BillType.hourly,
            PricingRule.seat_type == seat_type,
            PricingRule.is_active == 1,
        )
    )
    if not rule and seat_type != "standard":
        rule = db.scalar(
            select(PricingRule).where(
                PricingRule.store_id == reservation.store_id,
                PricingRule.bill_type == BillType.hourly,
                PricingRule.seat_type == "standard",
                PricingRule.is_active == 1,
            )
        )
    if rule:
        return (Decimal(str(rule.price)) * Decimal(extra_hours)).quantize(Decimal("0.01"))
    if reservation.original_price and reservation.duration_hours and reservation.duration_hours > 0:
        unit = Decimal(str(reservation.original_price)) / Decimal(str(reservation.duration_hours))
        return (unit * Decimal(extra_hours)).quantize(Decimal("0.01"))
    raise ValueError("门店未配置按小时续时价格，请联系店长")


def extend_reservation_with_balance(
    db: Session,
    reservation: Reservation,
    user: User,
    extra_hours: int,
) -> Decimal:
    """使用余额为预约续时：校验冲突、原子扣款、延长结束时间与蓝牙钥匙有效期。"""
    from app.core.redis_client import cache_delete
    from app.models import BleKey

    now = datetime.now()
    if reservation.pay_status != 1:
        raise ValueError("仅已付款订单可续时")
    if reservation.status not in (0, 1):
        raise ValueError("当前订单状态不可续时")
    if reservation.end_time <= now - timedelta(minutes=LATE_EXIT_MINUTES):
        raise ValueError("预约已结束，不可续时")

    new_end_time = reservation.end_time + timedelta(hours=extra_hours)
    conflict = seat_conflict_excluding(
        db,
        reservation.seat_id,
        reservation.end_time,
        new_end_time,
        exclude_reservation_id=reservation.id,
    )
    if conflict:
        raise ValueError("该座位后续时段已被预约，无法续时")

    extra_amount = calc_extend_price(db, reservation, extra_hours)
    if extra_amount > 0:
        if user.balance < extra_amount:
            raise ValueError("余额不足，请先充值后再续时")
        try:
            add_wallet_log(
                db,
                user,
                "consume",
                extra_amount,
                f"预约续时{extra_hours}小时-{reservation.order_no}",
                reservation.order_no,
            )
        except ValueError as exc:
            raise ValueError("余额不足，请先充值后再续时") from exc

    reservation.end_time = new_end_time
    reservation.duration_hours = (reservation.duration_hours or Decimal("0")) + Decimal(extra_hours)
    reservation.original_price = (reservation.original_price or Decimal("0")) + extra_amount
    reservation.final_price = (reservation.final_price or Decimal("0")) + extra_amount

    ble_keys = db.scalars(
        select(BleKey).where(BleKey.reservation_id == reservation.id, BleKey.status == 1)
    ).all()
    for key in ble_keys:
        key.end_time = new_end_time + timedelta(minutes=LATE_EXIT_MINUTES)
    cache_delete(f"ble_key:{reservation.id}")
    return extra_amount


async def finalize_reservation_after_pay(db: Session, reservation: Reservation) -> None:
    from app.services.business import create_ble_keys_for_reservation

    await create_ble_keys_for_reservation(db, reservation)
    auto_checkin_reservation(db, reservation)
    try:
        from app.services.subscribe_notify import send_booking_confirm_notify

        send_booking_confirm_notify(db, reservation)
    except Exception:
        logger.warning("booking confirm notify error res=%s", reservation.id, exc_info=True)
    db.commit()
