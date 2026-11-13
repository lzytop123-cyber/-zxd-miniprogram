import logging
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.redis_client import RedisLock
from app.db.session import get_db
from app.models import CardPurchaseOrder, Coupon, PayType, RechargeOrder, Reservation
from app.services.booking import finalize_reservation_after_pay, fulfill_recharge_order, seat_conflict_excluding
from app.services.card_service import fulfill_card_purchase
from app.services.coupon_service import mark_coupon_used
from app.services.pay_account import list_resolved_accounts_for_notify
from app.services.wechat_pay import WechatPayService, resolve_account_for_mchid
from app.services.receipts import payment_time

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


async def complete_reservation_wechat_payment(
    db: Session,
    reservation: Reservation,
    *,
    attach: str | None = None,
    paid_fen: int | None = None,
    success_time: str | None = None,
) -> str:
    """
    将预约标记为已支付并完成后续流程。
    返回: paid | conflict | amount_mismatch | already_paid
    """
    if reservation.pay_status in (1, 2):
        return "already_paid"
    if not _amount_ok(reservation.final_price, paid_fen):
        logger.error(
            "预约支付金额不符 %s 订单=%s 实付分=%s",
            reservation.order_no,
            reservation.final_price,
            paid_fen,
        )
        return "amount_mismatch"

    with RedisLock(f"seat_lock:{reservation.seat_id}", expire=10) as lock:
        if not lock.acquired:
            raise HTTPException(status_code=503, detail="座位正在处理中，请稍后重试")
        db.refresh(reservation, with_for_update=True)
        if reservation.pay_status in (1, 2):
            return "already_paid"
        reservation.paid_at = payment_time(success_time)
        reservation.pay_type = PayType.wechat
        conflict = seat_conflict_excluding(
            db,
            reservation.seat_id,
            reservation.start_time,
            reservation.end_time,
            reservation.id,
        )
        if conflict or reservation.status == 3:
            amount = reservation.final_price or Decimal("0")
            reservation.status = 3
            reservation.refund_remark = "微信退款尚未确认，等待重试或人工核对"
            db.commit()
            confirmed = False
            try:
                pay_acc = resolve_account_for_mchid(db, reservation.pay_mchid)
                if reservation.pay_mchid and pay_acc.mchid != reservation.pay_mchid:
                    raise ValueError("原收款商户不可用")
                confirmed = WechatPayService.refund(
                    reservation.order_no,
                    amount,
                    amount,
                    "座位冲突自动退款",
                    pay_account=pay_acc,
                    confirmed_refund_no=f"RF_CONFLICT_{reservation.order_no}",
                )
            except Exception:
                logger.exception("座位冲突自动退款失败 order_no=%s", reservation.order_no)
            if not confirmed:
                raise HTTPException(status_code=503, detail="预约已取消，退款结果待确认")
            reservation.pay_status = 2
            reservation.refunded_at = payment_time(None)
            reservation.refund_remark = "预约冲突或取消后到账，已原路退款"
            db.commit()
            return "conflict"

        reservation.pay_status = 1
        reservation.pay_type = PayType.wechat
        _apply_coupon_from_attach(db, reservation, attach)
        db.commit()

    await finalize_reservation_after_pay(db, reservation)
    return "paid"


def _mchid_mismatch(order_mchid: str | None, notify_mchid: str | None) -> bool:
    if not order_mchid or not notify_mchid:
        return False
    return order_mchid != notify_mchid


@router.post("/wechat/notify")
async def wechat_pay_notify(request: Request, db: Session = Depends(get_db)):
    """微信支付结果回调（生产环境需配置商户平台 notify_url）。"""
    body = await request.body()
    accounts = list_resolved_accounts_for_notify(db)
    result = WechatPayService.verify_notify(dict(request.headers), body, accounts=accounts)
    if not result:
        raise HTTPException(status_code=400, detail="invalid notify")

    order_no = result.get("out_trade_no")
    paid_fen = result.get("amount_total")
    notify_mchid = result.get("mchid")
    if order_no and result.get("trade_state") == "SUCCESS":
        if str(order_no).startswith("CRD"):
            order = db.scalar(select(CardPurchaseOrder).where(CardPurchaseOrder.order_no == order_no))
            if order and order.pay_status != 1:
                if _mchid_mismatch(order.pay_mchid, notify_mchid):
                    logger.error(
                        "回调商户号不符 CRD %s order=%s notify=%s",
                        order_no,
                        order.pay_mchid,
                        notify_mchid,
                    )
                    return {"code": "SUCCESS", "message": "成功"}
                if not _amount_ok(order.amount, paid_fen):
                    logger.error("回调金额不符 CRD %s 订单=%s 实付分=%s", order_no, order.amount, paid_fen)
                    return {"code": "SUCCESS", "message": "成功"}
                fulfill_card_purchase(db, order, success_time=result.get("success_time"))
                db.commit()
            return {"code": "SUCCESS", "message": "成功"}

        if str(order_no).startswith("RCH"):
            order = db.scalar(select(RechargeOrder).where(RechargeOrder.order_no == order_no))
            if order and order.pay_status != 1:
                if not _amount_ok(order.amount, paid_fen):
                    logger.error("回调金额不符 RCH %s 订单=%s 实付分=%s", order_no, order.amount, paid_fen)
                    return {"code": "SUCCESS", "message": "成功"}
                fulfill_recharge_order(db, order, success_time=result.get("success_time"))
                db.commit()
            return {"code": "SUCCESS", "message": "成功"}

        reservation = db.scalar(select(Reservation).where(Reservation.order_no == order_no))
        if reservation and reservation.pay_status != 1:
            if _mchid_mismatch(reservation.pay_mchid, notify_mchid):
                logger.error(
                    "回调商户号不符 RES %s order=%s notify=%s",
                    order_no,
                    reservation.pay_mchid,
                    notify_mchid,
                )
                return {"code": "SUCCESS", "message": "成功"}
            await complete_reservation_wechat_payment(
                db,
                reservation,
                attach=result.get("attach"),
                paid_fen=paid_fen,
                success_time=result.get("success_time"),
            )
    return {"code": "SUCCESS", "message": "成功"}
