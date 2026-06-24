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
    create_ble_keys_for_reservation,
    find_available_seat,
    generate_order_no,
)
from app.services.booking import add_wallet_log, record_study_on_checkout, resolve_booking_window, validate_seat_for_booking
from app.services.card_service import consume_period_card, validate_period_card_for_reservation
from app.services.coupon_service import apply_coupon, mark_coupon_used
from app.services.wechat_pay import WechatPayService

router = APIRouter(prefix="/reservation", tags=["预约"])


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
    )


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

    lock_key = f"seat_lock:{seat.id}:{start.strftime('%Y%m%d%H')}"
    with RedisLock(lock_key) as lock:
        if not lock.acquired:
            raise HTTPException(status_code=409, detail="座位正在被预约，请重试")

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
        reservation.final_price = Decimal("0.00")
        db.commit()
        await create_ble_keys_for_reservation(db, reservation)
        return ResponseModel(
            data=ReservationPayResponse(order_no=body.order_no, pay_type=PayType.period_card)
        )

    if body.pay_type == PayType.balance:
        if user.balance < (reservation.final_price or Decimal("0")):
            raise HTTPException(status_code=400, detail="余额不足")
        add_wallet_log(
            db, user, "consume", reservation.final_price or Decimal("0"),
            f"预约消费-{reservation.order_no}", reservation.order_no,
        )
        reservation.pay_type = PayType.balance
        reservation.pay_status = 1
        _mark_pay_coupon(db, user.id, body.coupon_id, reservation)
        db.commit()
        await create_ble_keys_for_reservation(db, reservation)
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
    await create_ble_keys_for_reservation(db, reservation)
    return ResponseModel(message="模拟支付成功")


@router.get("/list", response_model=ResponseModel[list[ReservationItem]])
def list_reservations(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(
        select(Reservation)
        .where(Reservation.user_id == user.id)
        .order_by(Reservation.created_at.desc())
        .limit(50)
    ).all()
    return ResponseModel(data=[_to_item(db, r) for r in rows])


@router.get("/active", response_model=ResponseModel[ReservationItem | None])
def active_reservation(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    now = datetime.now()
    row = db.scalar(
        select(Reservation)
        .where(
            Reservation.user_id == user.id,
            Reservation.pay_status == 1,
            Reservation.status.in_([0, 1]),
            Reservation.end_time > now,
        )
        .order_by(Reservation.start_time)
    )
    return ResponseModel(data=_to_item(db, row) if row else None)


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
    if reservation.pay_status == 1 and reservation.pay_type == PayType.wechat:
        WechatPayService.refund(
            reservation.order_no,
            reservation.final_price or Decimal("0"),
            reservation.final_price or Decimal("0"),
            "用户取消预约",
        )
        reservation.pay_status = 2
    db.commit()
    return ResponseModel(message="已取消")
