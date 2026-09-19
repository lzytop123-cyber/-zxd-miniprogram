"""收款的来源同步、日期口径与汇总。所有金额计算保留两位小数。"""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import CardPurchaseOrder, PayType, RechargeOrder, Reservation, User
from app.models.receipts import Receipt, ReceiptRefund

CHANNELS = {"meituan": "美团", "douyin": "抖音", "wechat_pay": "小程序微信支付", "wechat_transfer": "微信转账"}
BEIJING = timezone(timedelta(hours=8))


def today() -> date:
    return datetime.now(BEIJING).date()


def payment_time(success_time: str | None = None) -> datetime:
    """统一为北京时间墙钟；无平台时间时用确认时间。"""
    if success_time:
        value = datetime.fromisoformat(success_time.replace("Z", "+00:00"))
        if value.tzinfo is not None:
            return value.astimezone(BEIJING).replace(tzinfo=None)
        return value
    return datetime.now(BEIJING).replace(tzinfo=None)


def money(value) -> str:
    return format(Decimal(value or 0), ".2f")


def receipt_item(row: Receipt) -> dict:
    return {
        "id": row.id, "channel": row.channel, "amount": money(row.amount),
        "refunded_amount": money(row.refunded_amount),
        "remaining": money(row.amount - row.refunded_amount),
        "received_on": row.received_on, "customer": row.customer,
        "reference": row.reference, "remark": row.remark,
        "automatic": not row.source_key.startswith("manual:"),
        "source_label": "核销同步" if row.source_key.startswith("platform:") else ("手工登记" if row.source_key.startswith("manual:") else "微信同步"),
        "refund_needs_review": row.source_refunded and row.refunded_amount < row.amount,
    }


def refund_item(row: ReceiptRefund, receipt: Receipt) -> dict:
    return {
        "id": row.id, "receipt_id": row.receipt_id, "amount": money(row.amount),
        "refunded_on": row.refunded_on, "reason": row.reason, "status": "completed",
        "channel": receipt.channel, "customer": receipt.customer, "reference": receipt.reference,
    }


def period(year: int, month: int | None = None) -> tuple[date, date]:
    start = date(year, month or 1, 1)
    end = date(year + 1, 1, 1) if month is None or month == 12 else date(year, month + 1, 1)
    return start, end


def totals(db: Session, start: date, end: date, channel: str | None = None) -> dict:
    receipts = select(func.coalesce(func.sum(Receipt.amount), 0)).where(Receipt.received_on >= start, Receipt.received_on < end)
    refunds = select(func.coalesce(func.sum(ReceiptRefund.amount), 0)).join(Receipt).where(ReceiptRefund.refunded_on >= start, ReceiptRefund.refunded_on < end)
    if channel:
        receipts = receipts.where(Receipt.channel == channel)
        refunds = refunds.where(Receipt.channel == channel)
    received, refunded = db.scalar(receipts), db.scalar(refunds)
    return {"received": money(received), "refunded": money(refunded), "net": money(received - refunded)}


def sync_wechat(db: Session) -> int:
    """显式同步：只导入成功现金支付，唯一来源键保证重试/并发不重复。"""
    added = 0
    for model, prefix, label in (
        (Reservation, "reservation:", "预约支付"),
        (CardPurchaseOrder, "card:", "套餐购买"),
        (RechargeOrder, "recharge:", "余额充值"),
    ):
        amount_col = model.final_price if model is Reservation else model.amount
        source_key = prefix + model.order_no
        query = (
            select(model, User.nickname, Receipt)
            .outerjoin(User, User.id == model.user_id)
            .outerjoin(Receipt, Receipt.source_key == source_key)
            .where(model.pay_type == PayType.wechat, model.pay_status.in_([1, 2]), amount_col > 0)
            .where(or_(Receipt.id.is_(None), (model.pay_status == 2) & (Receipt.source_refunded == False)))
        )
        for order, nickname, existing in db.execute(query).all():
            if existing:
                existing.source_refunded = order.pay_status == 2
                continue
            row = Receipt(
                source_key=prefix + order.order_no, channel="wechat_pay",
                amount=order.final_price if model is Reservation else order.amount,
                received_on=order.paid_at.date() if order.paid_at else None,
                customer=nickname or f"用户 {order.user_id}", reference=order.order_no,
                remark=label, source_refunded=order.pay_status == 2,
            )
            try:
                with db.begin_nested():
                    db.add(row)
                    db.flush()
                added += 1
            except IntegrityError:
                # A parallel sync may already have inserted the same source.
                if not db.scalar(select(Receipt.id).where(Receipt.source_key == row.source_key)):
                    raise
    return added
