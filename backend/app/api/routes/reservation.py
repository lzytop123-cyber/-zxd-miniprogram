from datetime import datetime, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.prod import block_mock_in_production
from app.core.redis_client import RedisLock
from app.db.session import get_db
from app.models import BillType, Coupon, PayType, PeriodCard, Reservation, Seat, Store, User
from app.schemas.common import ResponseModel
from app.schemas.reservation import (
    ReservationCreateRequest,
    ReservationItem,
    ReservationPayRequest,
    ReservationPayResponse,
    ReservationPreviewRequest,
    ReservationPreviewResponse,
    WechatPayParams,
)
from app.services.business import (
    calc_price,
    find_available_seat,
    generate_order_no,
)
from app.services.booking import (
    add_wallet_log,
    auto_checkin_reservation,
    finalize_expired_reservation,
    finalize_reservation_after_pay,
    record_study_on_checkout,
    reservation_status_display,
    reservation_unlock_allowed,
    resolve_booking_window,
    seat_conflict_excluding,
    validate_seat_for_booking,
)
from app.services.card_service import (
    consume_period_card,
    refund_period_card_consume,
    validate_period_card_for_reservation,
)
from app.services.coupon_service import apply_coupon, mark_coupon_used
from app.services.wechat_pay import WechatPayService

router = APIRouter(prefix="/reservation", tags=["预约"])

SEAT_LOCK_EXPIRE = 10


def _seat_lock(seat_id: int) -> RedisLock:
    """同一座位的预约/支付串行化锁（覆盖整个座位，避免跨时段超卖）。"""
    return RedisLock(f"seat_lock:{seat_id}", expire=SEAT_LOCK_EXPIRE)


def _prepare_booking(db: Session, body, require_seat: bool = False):
    """统一计算预约时段、价格、座位。"""
    rule = None
    try:
        _, rule = calc_price(db, body.store_id, body.bill_type, Decimal("1"))
    except ValueError:
        pass
    start, end = resolve_booking_window(body.bill_type, body.start_time, body.end_time, rule)
    if body.bill_type == BillType.session:
        duration = Decimal(str((end.date() - start.date()).days + 1))
    else:
        duration = Decimal(str((end - start).total_seconds() / 3600)).quantize(Decimal("0.01"))

    seat = None
    if body.seat_id:
        seat = db.get(Seat, body.seat_id)
    elif not require_seat:
        seat = find_available_seat(db, body.store_id, start, end)
    if require_seat and not body.seat_id:
        raise HTTPException(status_code=400, detail="请选择座位")
    if seat:
        try:
            seat = validate_seat_for_booking(db, seat, body.store_id, start, end)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    elif not require_seat:
        raise HTTPException(status_code=400, detail="暂无可用座位")

    try:
        price, _ = calc_price(db, body.store_id, body.bill_type, duration)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return start, end, duration, seat, price


def _mark_pay_coupon(
    db: Session,
    user_id: int,
    coupon_id: int | None,
    reservation: Reservation,
) -> None:
    if not coupon_id:
        return
    coupon = db.get(Coupon, coupon_id)
    if coupon and coupon.user_id == user_id and coupon.status == 0:
        mark_coupon_used(db, coupon, reservation)


def _resolve_coupon_price(
    db: Session,
    user_id: int,
    coupon_id: int | None,
    original_price: Decimal,
) -> tuple[Decimal, Decimal, Coupon | None]:
    if not coupon_id:
        return Decimal("0.00"), original_price, None
    coupon = db.get(Coupon, coupon_id)
    if not coupon or coupon.user_id != user_id:
        raise HTTPException(status_code=400, detail="优惠券不存在")
    try:
        discount, final_price = apply_coupon(original_price, coupon)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return discount, final_price, coupon


def _to_item(db: Session, r: Reservation) -> ReservationItem:
    seat = db.get(Seat, r.seat_id)
    store = db.get(Store, r.store_id)
    label, hint = reservation_status_display(r)
    return ReservationItem(
        id=r.id,
        order_no=r.order_no,
        store_id=r.store_id,
        seat_id=r.seat_id,
        seat_code=seat.seat_code if seat else None,
        store_name=store.name if store else None,
        bill_type=r.bill_type,
        start_time=r.start_time,
        end_time=r.end_time,
        final_price=r.final_price,
        pay_status=r.pay_status,
        status=r.status,
        check_in_time=r.check_in_time,
        created_at=r.created_at,
        status_label=label,
        status_hint=hint,
    )


def _sync_user_active_reservations(
    db: Session,
    user: User,
    now: datetime | None = None,
) -> list[Reservation]:
    """完结已过期订单，返回用户全部进行中预约（按开始时间排序）。"""
    now = now or datetime.now()
    stale = db.scalars(
        select(Reservation).where(
            Reservation.user_id == user.id,
            Reservation.pay_status == 1,
            Reservation.status.in_([0, 1]),
            Reservation.end_time <= now,
        )
    ).all()
    changed = False
    for row in stale:
        if finalize_expired_reservation(db, row, now):
            changed = True

    rows = db.scalars(
        select(Reservation)
        .where(
            Reservation.user_id == user.id,
            Reservation.pay_status == 1,
            Reservation.status.in_([0, 1]),
            Reservation.end_time > now,
        )
        .order_by(Reservation.start_time)
    ).all()
    for row in rows:
        if auto_checkin_reservation(db, row, when=now):
            changed = True
    if changed:
        db.commit()
        for row in rows:
            db.refresh(row)
    return rows


def _assert_seat_available_for_pay(db: Session, reservation: Reservation) -> None:
    conflict = seat_conflict_excluding(
        db,
        reservation.seat_id,
        reservation.start_time,
        reservation.end_time,
        reservation.id,
    )
    if conflict:
        raise HTTPException(status_code=409, detail="该座位已被他人预约，请重新选座")


@router.post("/preview", response_model=ResponseModel[ReservationPreviewResponse])
def preview(
    body: ReservationPreviewRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    start, end, duration, seat, price = _prepare_booking(db, body)
    discount, final_price, _ = _resolve_coupon_price(db, user.id, body.coupon_id, price)
    return ResponseModel(
        data=ReservationPreviewResponse(
            store_id=body.store_id,
            seat_id=seat.id,
            seat_code=seat.seat_code,
            bill_type=body.bill_type,
            start_time=start,
            end_time=end,
            duration_hours=duration,
            original_price=price,
            discount_price=discount,
            final_price=final_price,
        )
    )


@router.post("/create", response_model=ResponseModel[ReservationItem])
def create(
    body: ReservationCreateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    start, end, duration, seat, price = _prepare_booking(db, body, require_seat=bool(body.seat_id))
    discount, final_price, coupon = _resolve_coupon_price(db, user.id, body.coupon_id, price)

    with _seat_lock(seat.id) as lock:
        if not lock.acquired:
            raise HTTPException(status_code=409, detail="座位正在被预约，请重试")

        # 锁内二次校验，避免与已支付订单时段冲突（防超卖）
        if seat_conflict_excluding(db, seat.id, start, end):
            raise HTTPException(status_code=409, detail="该座位时段已被预约，请重新选座")

        reservation = Reservation(
            order_no=generate_order_no(),
            user_id=user.id,
            store_id=body.store_id,
            seat_id=seat.id,
            bill_type=body.bill_type,
            start_time=start,
            end_time=end,
            duration_hours=duration,
            original_price=price,
            discount_price=discount,
            final_price=final_price,
            pay_status=0,
            status=0,
        )
        db.add(reservation)
        db.commit()
        db.refresh(reservation)
        return ResponseModel(data=_to_item(db, reservation))


@router.post("/pay", response_model=ResponseModel[ReservationPayResponse])
async def pay(
    body: ReservationPayRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    reservation = db.scalar(
        select(Reservation).where(
            Reservation.order_no == body.order_no, Reservation.user_id == user.id
        )
    )
    if not reservation:
        raise HTTPException(status_code=404, detail="订单不存在")
    if reservation.pay_status == 1:
        raise HTTPException(status_code=400, detail="订单已支付")

    _assert_seat_available_for_pay(db, reservation)

    if body.pay_type == PayType.period_card:
        if not body.period_card_id:
            raise HTTPException(status_code=400, detail="请选择期限卡")
        card = db.get(PeriodCard, body.period_card_id)
        if not card or card.user_id != user.id:
            raise HTTPException(status_code=404, detail="期限卡不存在")
        try:
            validate_period_card_for_reservation(
                db,
                card,
                reservation.bill_type,
                reservation.start_time,
                reservation.end_time,
                reservation.store_id,
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        with _seat_lock(reservation.seat_id) as lock:
            if not lock.acquired:
                raise HTTPException(status_code=409, detail="座位正在被占用，请重试")
            _assert_seat_available_for_pay(db, reservation)
            consume_period_card(
                db,
                card,
                reservation.bill_type,
                reservation.start_time,
                reservation.end_time,
                reservation.store_id,
            )
            reservation.pay_type = PayType.period_card
            reservation.pay_status = 1
            reservation.period_card_id = card.id
            reservation.final_price = Decimal("0.00")
            db.commit()
        await finalize_reservation_after_pay(db, reservation)
        return ResponseModel(
            data=ReservationPayResponse(order_no=body.order_no, pay_type=PayType.period_card)
        )

    if body.pay_type == PayType.balance:
        if user.balance < (reservation.final_price or Decimal("0")):
            raise HTTPException(status_code=400, detail="余额不足")
        with _seat_lock(reservation.seat_id) as lock:
            if not lock.acquired:
                raise HTTPException(status_code=409, detail="座位正在被占用，请重试")
            _assert_seat_available_for_pay(db, reservation)
            try:
                add_wallet_log(
                    db, user, "consume", reservation.final_price or Decimal("0"),
                    f"预约消费-{reservation.order_no}", reservation.order_no,
                )
            except ValueError:
                raise HTTPException(status_code=400, detail="余额不足")
            reservation.pay_type = PayType.balance
            reservation.pay_status = 1
            _mark_pay_coupon(db, user.id, body.coupon_id, reservation)
            db.commit()
        await finalize_reservation_after_pay(db, reservation)
        return ResponseModel(
            data=ReservationPayResponse(order_no=body.order_no, pay_type=PayType.balance)
        )

    if body.pay_type == PayType.wechat:
        reservation.pay_type = PayType.wechat
        db.commit()
        attach = f"coupon_id={body.coupon_id}" if body.coupon_id else None
        try:
            pay_params = WechatPayService.create_jsapi_order(
                body.order_no,
                reservation.final_price or Decimal("0"),
                user.openid,
                f"知行岛自习室-{reservation.order_no}",
                attach=attach,
            )
        except RuntimeError as e:
            raise HTTPException(status_code=502, detail=str(e))
        return ResponseModel(
            data=ReservationPayResponse(
                order_no=body.order_no,
                pay_type=PayType.wechat,
                wechat_pay=WechatPayParams(**pay_params),
            )
        )

    raise HTTPException(status_code=400, detail="不支持的支付方式")


@router.post("/{reservation_id}/mock-pay", response_model=ResponseModel)
async def mock_pay(
    reservation_id: int,
    coupon_id: int | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """开发环境模拟支付成功"""
    block_mock_in_production()
    reservation = db.get(Reservation, reservation_id)
    if not reservation or reservation.user_id != user.id:
        raise HTTPException(status_code=404, detail="订单不存在")
    reservation.pay_status = 1
    reservation.pay_type = PayType.wechat
    _mark_pay_coupon(db, user.id, coupon_id, reservation)
    db.commit()
    await finalize_reservation_after_pay(db, reservation)
    return ResponseModel(message="模拟支付成功")


@router.get("/list", response_model=ResponseModel[list[ReservationItem]])
def list_reservations(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(
        select(Reservation)
        .where(Reservation.user_id == user.id)
        .order_by(Reservation.created_at.desc())
        .limit(50)
    ).all()
    changed = False
    for row in rows:
        if auto_checkin_reservation(db, row):
            changed = True
    if changed:
        db.commit()
    return ResponseModel(data=[_to_item(db, r) for r in rows])


@router.get("/active/list", response_model=ResponseModel[list[ReservationItem]])
def list_active_reservations(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    now = datetime.now()
    rows = _sync_user_active_reservations(db, user, now)
    return ResponseModel(data=[_to_item(db, row) for row in rows])


@router.get("/active", response_model=ResponseModel[ReservationItem | None])
def active_reservation(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    now = datetime.now()
    rows = _sync_user_active_reservations(db, user, now)
    if not rows:
        return ResponseModel(data=None)
    row = rows[0]
    if not reservation_unlock_allowed(row, now):
        return ResponseModel(data=None)
    return ResponseModel(data=_to_item(db, row))


@router.get("/{reservation_id}", response_model=ResponseModel[ReservationItem])
def get_reservation(
    reservation_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    reservation = db.get(Reservation, reservation_id)
    if not reservation or reservation.user_id != user.id:
        raise HTTPException(status_code=404, detail="订单不存在")
    return ResponseModel(data=_to_item(db, reservation))


@router.post("/{reservation_id}/checkin", response_model=ResponseModel)
def checkin(
    reservation_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    reservation = db.get(Reservation, reservation_id)
    if not reservation or reservation.user_id != user.id:
        raise HTTPException(status_code=404, detail="订单不存在")
    if reservation.pay_status != 1:
        raise HTTPException(status_code=400, detail="订单未支付")
    reservation.status = 1
    reservation.check_in_time = datetime.now()
    db.commit()
    return ResponseModel(message="入座成功")


@router.post("/{reservation_id}/checkout", response_model=ResponseModel)
def checkout(
    reservation_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    reservation = db.get(Reservation, reservation_id)
    if not reservation or reservation.user_id != user.id:
        raise HTTPException(status_code=404, detail="订单不存在")
    reservation.status = 2
    reservation.actual_end_time = datetime.now()
    record_study_on_checkout(db, reservation, user)
    db.commit()
    return ResponseModel(message="已离座")


@router.post("/{reservation_id}/cancel", response_model=ResponseModel)
def cancel(
    reservation_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    reservation = db.get(Reservation, reservation_id)
    if not reservation or reservation.user_id != user.id:
        raise HTTPException(status_code=404, detail="订单不存在")
    if reservation.status not in (0,):
        raise HTTPException(status_code=400, detail="当前状态不可取消")
    reservation.status = 3
    if reservation.pay_status == 0:
        db.commit()
        return ResponseModel(message="已取消")

    if reservation.pay_status == 1:
        amount = reservation.final_price or Decimal("0")
        if reservation.pay_type == PayType.wechat:
            if amount > 0:
                WechatPayService.refund(reservation.order_no, amount, amount, "用户取消预约")
            reservation.pay_status = 2
        elif reservation.pay_type == PayType.balance:
            if amount > 0:
                add_wallet_log(
                    db, user, "refund", amount,
                    f"取消退款-{reservation.order_no}", reservation.order_no,
                )
            reservation.pay_status = 2
        elif reservation.pay_type == PayType.period_card:
            if reservation.period_card_id:
                card = db.get(PeriodCard, reservation.period_card_id)
                if card:
                    refund_period_card_consume(
                        card, reservation.bill_type, reservation.start_time, reservation.end_time
                    )
            reservation.pay_status = 2
        reservation.refunded_at = datetime.now()
        reservation.refund_remark = "用户取消预约"
    db.commit()
    return ResponseModel(message="已取消")
