import logging
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.redis_client import RedisLock
from app.db.session import get_db
from app.models import CardPurchaseOrder, Coupon, PayType, RechargeOrder, Reservation
from app.services.booking import (
    auto_checkin_reservation,
    finalize_reservation_after_pay,
    fulfill_recharge_order,
    seat_conflict_excluding,
)
from app.services.card_service import fulfill_card_purchase
from app.services.coupon_service import mark_coupon_used
from app.services.wechat_pay import WechatPayService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/payment", tags=["支付"])


def _amount_ok(expected: Decimal | None, paid_fen) -> bool:
    """校验微信实付金额（分）与订单金额一致；mock 或未提供金额时跳过。"""
    if paid_fen is None:
        return True
    try:
        return int((Decimal(str(expected or 0)) * 100).quantize(Decimal("1"))) == int(paid_fen)
    except Exception:
        return False


def _apply_coupon_from_attach(db: Session, reservation: Reservation, attach: str | None) -> None:
    if not attach or not attach.startswith("coupon_id="):
        return
    try:
        coupon_id = int(attach.split("=", 1)[1])
    except ValueError:
        return
    coupon = db.get(Coupon, coupon_id)
    if coupon and coupon.user_id == reservation.user_id and coupon.status == 0:
        mark_coupon_used(db, coupon, reservation)


@router.post("/wechat/notify")
async def wechat_pay_notify(request: Request, db: Session = Depends(get_db)):
    """微信支付结果回调（生产环境需配置商户平台 notify_url）。"""
    body = await request.body()
    result = WechatPayService.verify_notify(dict(request.headers), body)
    if not result:
        raise HTTPException(status_code=400, detail="invalid notify")

    order_no = result.get("out_trade_no")
    paid_fen = result.get("amount_total")
    if order_no and result.get("trade_state") == "SUCCESS":
        if str(order_no).startswith("CRD"):
            order = db.scalar(select(CardPurchaseOrder).where(CardPurchaseOrder.order_no == order_no))
            if order and order.pay_status != 1:
                if not _amount_ok(order.amount, paid_fen):
                    logger.error("回调金额不符 CRD %s 订单=%s 实付分=%s", order_no, order.amount, paid_fen)
                    return {"code": "SUCCESS", "message": "成功"}
                fulfill_card_purchase(db, order)
                db.commit()
            return {"code": "SUCCESS", "message": "成功"}

        if str(order_no).startswith("RCH"):
            order = db.scalar(select(RechargeOrder).where(RechargeOrder.order_no == order_no))
            if order and order.pay_status != 1:
                if not _amount_ok(order.amount, paid_fen):
                    logger.error("回调金额不符 RCH %s 订单=%s 实付分=%s", order_no, order.amount, paid_fen)
                    return {"code": "SUCCESS", "message": "成功"}
                fulfill_recharge_order(db, order)
                db.commit()
            return {"code": "SUCCESS", "message": "成功"}

        reservation = db.scalar(select(Reservation).where(Reservation.order_no == order_no))
        if reservation and reservation.pay_status != 1:
            if not _amount_ok(reservation.final_price, paid_fen):
                logger.error(
                    "回调金额不符 预约 %s 订单=%s 实付分=%s",
                    order_no, reservation.final_price, paid_fen,
                )
                return {"code": "SUCCESS", "message": "成功"}
            with RedisLock(f"seat_lock:{reservation.seat_id}", expire=10):
                conflict = seat_conflict_excluding(
                    db,
                    reservation.seat_id,
                    reservation.start_time,
                    reservation.end_time,
                    reservation.id,
                )
                if conflict:
                    # 座位已被他人占用：自动退款并取消，避免超卖/重复占座
                    amount = reservation.final_price or Decimal("0")
                    try:
                        WechatPayService.refund(order_no, amount, amount, "座位冲突自动退款")
                    except Exception:
                        logger.exception("座位冲突自动退款失败 order_no=%s", order_no)
                    reservation.status = 3
                    reservation.pay_status = 2
                    db.commit()
                    return {"code": "SUCCESS", "message": "成功"}

                reservation.pay_status = 1
                reservation.pay_type = PayType.wechat
                _apply_coupon_from_attach(db, reservation, result.get("attach"))
                db.commit()
            await finalize_reservation_after_pay(db, reservation)
    return {"code": "SUCCESS", "message": "成功"}
