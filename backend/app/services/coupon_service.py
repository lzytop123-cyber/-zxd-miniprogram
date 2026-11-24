from datetime import date
from decimal import Decimal

from sqlalchemy import and_, or_, select, update
from sqlalchemy.orm import Session

from app.models import Coupon, Reservation


def apply_coupon(
    original_price: Decimal,
    coupon: Coupon | None,
) -> tuple[Decimal, Decimal]:
    if not coupon:
        return Decimal("0.00"), original_price
    if coupon.status != 0:
        raise ValueError("优惠券不可用")
    if coupon.expire_date and date.today() > coupon.expire_date:
        raise ValueError("优惠券已过期")
    if original_price < (coupon.min_amount or Decimal("0")):
        raise ValueError(f"未满 {coupon.min_amount} 元不可使用该券")

    discount = Decimal("0.00")
    if coupon.discount_type == "percent":
        discount = (original_price * (coupon.discount_val or Decimal("0")) / Decimal("100")).quantize(
            Decimal("0.01")
        )
    elif coupon.discount_type == "amount":
        discount = min(coupon.discount_val or Decimal("0"), original_price)

    final_price = max(original_price - discount, Decimal("0.00"))
    return discount, final_price


def mark_coupon_used(db: Session, coupon: Coupon, reservation: Reservation) -> bool:
    """只核销可用券或本订单预占券，并保留核销归属。"""
    result = db.execute(
        update(Coupon).where(
            Coupon.id == coupon.id,
            Coupon.user_id == reservation.user_id,
            or_(Coupon.status == 0, and_(Coupon.status == 2, Coupon.reserved_order_no == reservation.order_no)),
        ).values(status=1, reserved_order_no=reservation.order_no)
    )
    if result.rowcount == 1:
        reservation.coupon_id = coupon.id
        db.refresh(coupon)
        return True
    return False


def claim_reservation_coupon(db: Session, reservation: Reservation, *, reserve: bool = False) -> None:
    """以持久化订单为准校验、占用或核销；失败时不得按折后价付款。"""
    if not getattr(reservation, "coupon_id", None):
        return
    coupon = db.scalar(select(Coupon).where(Coupon.id == reservation.coupon_id).with_for_update()
                       .execution_options(populate_existing=True))
    if not coupon or coupon.user_id != reservation.user_id:
        raise ValueError("订单优惠券不存在")
    owned = coupon.reserved_order_no == reservation.order_no
    if coupon.status == 2 and owned:
        if reserve:
            return
    elif coupon.status == 0:
        discount, final_price = apply_coupon(reservation.original_price, coupon)
        if final_price != reservation.final_price or discount != reservation.discount_price:
            raise ValueError("优惠券价格已变化，请重新下单")
    else:
        raise ValueError("优惠券已使用或被其他订单占用，请重新下单")
    if reserve:
        result = db.execute(update(Coupon).where(Coupon.id == coupon.id, Coupon.status == 0)
                            .values(status=2, reserved_order_no=reservation.order_no))
        if result.rowcount != 1:
            raise ValueError("优惠券已被占用，请重新下单")
        db.refresh(coupon)
    elif not mark_coupon_used(db, coupon, reservation):
        raise ValueError("优惠券核销失败，请重试")


def refund_coupon_for_reservation(db: Session, reservation: Reservation) -> bool:
    """仅释放本订单预占券或已确认退款的已用券。"""
    if not getattr(reservation, "coupon_id", None):
        return False
    coupon = db.get(Coupon, reservation.coupon_id)
    if not coupon or reservation.status != 3:
        return False
    owned = coupon.reserved_order_no == reservation.order_no
    # 兼容升级前已核销但尚无归属字段的历史订单。
    legacy = coupon.reserved_order_no is None and reservation.pay_status == 2
    if not owned and not legacy:
        return False
    if coupon.status != 2 and not (coupon.status == 1 and reservation.pay_status == 2):
        return False
    if legacy and db.scalar(select(Reservation.id).where(
        Reservation.coupon_id == coupon.id, Reservation.id != reservation.id, Reservation.pay_status == 1,
    ).limit(1)):
        return False
    result = db.execute(update(Coupon).where(
        Coupon.id == coupon.id, Coupon.status == coupon.status,
        Coupon.reserved_order_no == coupon.reserved_order_no,
    ).values(status=0, reserved_order_no=None))
    return result.rowcount == 1
