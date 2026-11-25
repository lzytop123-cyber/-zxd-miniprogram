"""Shared cancellation/refund transition for user and administrative requests."""
import logging
from datetime import datetime
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DoorLog, PayType, PeriodCard, Reservation, User
from app.services.booking import add_wallet_log
from app.services.card_service import refund_period_card_consume
from app.services.coupon_service import refund_coupon_for_reservation
from app.services.wechat_pay import WechatPayService, resolve_account_for_mchid

logger = logging.getLogger(__name__)
REFUND_PENDING = "微信退款尚未确认，等待重试或人工核对"


def cancel_reservation(db: Session, reservation: Reservation, user: User | None, reason: str) -> str:
    db.refresh(reservation, with_for_update=True)
    conflict_refund = reservation.pay_status == 0 and reservation.paid_at is not None
    pending = (reservation.status == 3 and reservation.pay_type == PayType.wechat
               and (reservation.pay_status == 1 or conflict_refund))
    if reservation.status == 3 and not pending:
        if reservation.pay_status == 0 and reservation.paid_at is None:
            refund_coupon_for_reservation(db, reservation)
            db.commit()
        return "订单已取消"
    can_cancel = reservation.status == 0
    if not can_cancel and reservation.status == 1 and datetime.now() < reservation.start_time:
        opened = db.scalar(
            select(DoorLog.id).where(
                DoorLog.reservation_id == reservation.id,
                DoorLog.result == 1,
            ).limit(1)
        )
        if opened is None:
            can_cancel = True
    if not can_cancel and not pending:
        raise HTTPException(status_code=400, detail="当前状态不可取消")
    reservation.status = 3
    if reservation.pay_status == 0 and not conflict_refund:
        refund_coupon_for_reservation(db, reservation)
        db.commit()
        return "未支付订单已取消，座位已释放"
    amount = reservation.final_price or Decimal("0")
    if reservation.pay_type == PayType.admin:
        db.commit()
        return "已取消，前台收款订单不退款"
    if reservation.pay_type == PayType.wechat:
        reservation.refund_remark = REFUND_PENDING
        # 冻结预约并保留真实支付状态，外部退款失败或超时后仍能用同一退款单重试。
        db.commit()
        confirmed = amount <= 0
        if not confirmed:
            try:
                account = resolve_account_for_mchid(db, reservation.pay_mchid)
                if reservation.pay_mchid and account.mchid != reservation.pay_mchid:
                    raise ValueError("原收款商户不可用")
                prefix = "RF_CONFLICT_" if conflict_refund else "RF_CANCEL_"
                confirmed = WechatPayService.refund(
                    reservation.order_no, amount, amount, reason, pay_account=account,
                    confirmed_refund_no=f"{prefix}{reservation.order_no}",
                )
            except Exception:
                logger.exception("reservation refund pending order_no=%s", reservation.order_no)
        if not confirmed:
            raise HTTPException(status_code=503, detail="预约已取消，退款结果待确认，可稍后重试")
        db.refresh(reservation, with_for_update=True)
    elif reservation.pay_type == PayType.balance:
        if user is None:
            raise HTTPException(status_code=400, detail="用户不存在，无法退还余额")
        if amount > 0:
            add_wallet_log(db, user, "refund", amount, f"预约退款-{reservation.order_no}", reservation.order_no)
    elif reservation.pay_type == PayType.period_card and reservation.period_card_id:
        card = db.get(PeriodCard, reservation.period_card_id)
        if card:
            refund_period_card_consume(card, reservation.bill_type, reservation.start_time, reservation.end_time)
    reservation.pay_status = 2
    reservation.refunded_at = datetime.now()
    reservation.refund_remark = reason
    refund_coupon_for_reservation(db, reservation)
    db.commit()
    return "订单已取消，退款已确认"
