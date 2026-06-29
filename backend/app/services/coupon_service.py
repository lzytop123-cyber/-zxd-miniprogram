from datetime import date
from decimal import Decimal

from sqlalchemy import update
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
    """原子核销优惠券：仅当券仍为未使用(status=0)时置为已用，防并发重复使用。"""
    result = db.execute(
        update(Coupon).where(Coupon.id == coupon.id, Coupon.status == 0).values(status=1)
    )
    if result.rowcount == 1:
        db.refresh(coupon)
        return True
    return False
