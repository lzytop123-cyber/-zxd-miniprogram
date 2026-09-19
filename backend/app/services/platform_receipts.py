"""将已核销券关联到收款台账；参考价仅供核对，不自动记账。"""
import json
from decimal import Decimal, InvalidOperation

from sqlalchemy import String, cast, literal, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import CardSource, MeituanOrder, MeituanOrderStatus, PeriodCard, User
from app.models.receipts import Receipt
from app.services.receipts import money, today

ELIGIBLE = [MeituanOrderStatus.verified, MeituanOrderStatus.refunded]


def source_key(order_id: int) -> str:
    return f"platform:{order_id}"


def reference(order: MeituanOrder) -> str:
    code = order.coupon_code or order.meituan_order_id
    return code if code and len(code) <= 100 else source_key(order.id)


def paid_amount(raw: dict) -> tuple[Decimal | None, str]:
    """只接受明确支付字段；不使用 dealPrice、原价、市场价或券补贴金额。

    已有适配器将 payAmount / amount.pay_amount 按分处理。多券/次卡的
    整单金额无法安全分摊到一次核销，因此交由人工核对。
    """
    values = []
    ambiguous = False

    def visit(node):
        nonlocal ambiguous
        if isinstance(node, str):
            try:
                node = json.loads(node)
            except (ValueError, TypeError):
                return
        if not isinstance(node, dict):
            return
        if node.get("time_card"):
            ambiguous = True
        if "payAmount" in node and node["payAmount"] is not None:
            values.append(node["payAmount"])
        amount = node.get("amount")
        if isinstance(amount, dict) and "pay_amount" in amount and amount["pay_amount"] is not None:
            values.append(amount["pay_amount"])
        for key in ("ticketData", "raw_prepare", "_certificate_get", "certificate", "data", "result", "verify_result", "raw_verify"):
            visit(node.get(key))
        for key in ("certificates", "certificates_v2", "verify_results"):
            items = node.get(key)
            if isinstance(items, list):
                if len(items) > 1:
                    ambiguous = True
                elif items:
                    visit(items[0])

    visit(raw)
    if ambiguous:
        return None, "多券或次卡金额需核对本次核销分摊"
    if not values:
        return None, "缺少明确实付金额，原价/团购价仅供参考"
    parsed = []
    for value in values:
        try:
            fen = Decimal(str(value))
            if not fen.is_finite() or fen < 0 or fen >= 10000000000 or fen != fen.to_integral_value():
                return None, "接口支付金额格式异常"
            parsed.append(fen / 100)
        except (InvalidOperation, ValueError):
            return None, "接口支付金额格式异常"
    if len(set(parsed)) != 1:
        return None, "接口中的支付金额不一致"
    if parsed[0] == 0:
        return None, "接口实付为零，请核对；不会回退到原价入账"
    return parsed[0], ""


def candidates(db: Session) -> list[dict]:
    key = literal("platform:") + cast(MeituanOrder.id, String)
    rows = db.execute(
        select(MeituanOrder, User.nickname)
        .outerjoin(User, User.id == MeituanOrder.user_id)
        .outerjoin(Receipt, Receipt.source_key == key)
        .where(MeituanOrder.status.in_(ELIGIBLE), Receipt.id.is_(None))
        .order_by(MeituanOrder.id.desc())
    ).all()
    if not rows:
        return []
    codes = [row.coupon_code for row, _ in rows if row.coupon_code]
    sources: dict[tuple, set] = {}
    for code, user_id, source in db.execute(select(PeriodCard.meituan_receipt, PeriodCard.user_id, PeriodCard.source).where(PeriodCard.meituan_receipt.in_(codes))):
        if source in (CardSource.meituan, CardSource.douyin):
            sources.setdefault((code, user_id), set()).add(source.value)
    refs = {reference(row) for row, _ in rows} | {row.meituan_order_id for row, _ in rows if row.meituan_order_id}
    existing = {(r.channel, r.reference): r.id for r in db.scalars(select(Receipt).where(Receipt.channel.in_(["meituan", "douyin"]), Receipt.reference.in_(refs))).all()}
    result = []
    for order, nickname in rows:
        raw = order.meituan_raw if isinstance(order.meituan_raw, dict) else {}
        channels = set(sources.get((order.coupon_code, order.user_id), set()))
        if raw.get("receipt_channel") in ("meituan", "douyin"):
            channels.add(raw["receipt_channel"])
        if raw.get("platform") == "douyin_official":
            channels.add("douyin")
        channel = next(iter(channels)) if len(channels) == 1 else None
        amount, amount_reason = paid_amount(raw)
        day = order.verified_at.date() if order.verified_at else None
        duplicate = existing.get((channel, reference(order))) or existing.get((channel, order.meituan_order_id))
        reasons = [amount_reason] if amount_reason else []
        if not channel:
            reasons.append("渠道缺失或冲突，请确认美团/抖音")
        if not day or day > today():
            reasons.append("缺少有效核销日期")
        if duplicate:
            reasons.append(f"流水号已登记在收款 #{duplicate}，请关联原记录")
        reference_price = order.deal_price
        if reference_price is not None and (not reference_price.is_finite() or reference_price < 0):
            reference_price = None
        result.append({
            "id": order.id, "channel": channel, "amount": money(amount) if amount is not None else None,
            "reference_price": money(reference_price) if reference_price is not None else None,
            "received_on": day, "reference": reference(order), "customer": nickname or "",
            "deal_name": order.deal_name or "", "reason": "；".join(reasons),
            "existing_receipt_id": duplicate, "ready": not reasons,
            "source_refunded": order.status == MeituanOrderStatus.refunded,
        })
    return result


def sync_platforms(db: Session) -> int:
    # Refund status is a review hint, never proof of money returned.
    refunded_keys = select(literal("platform:") + cast(MeituanOrder.id, String)).where(MeituanOrder.status == MeituanOrderStatus.refunded)
    db.execute(update(Receipt).where(Receipt.source_key.in_(refunded_keys), Receipt.source_refunded == False).values(source_refunded=True))
    added = 0
    for item in candidates(db):
        if not item["ready"]:
            continue
        row = Receipt(
            source_key=source_key(item["id"]), channel=item["channel"], amount=Decimal(item["amount"]),
            received_on=item["received_on"], reference=item["reference"], customer=item["customer"],
            remark=f"核销收款 · {item['deal_name']}"[:500], source_refunded=item["source_refunded"],
        )
        try:
            with db.begin_nested():
                db.add(row)
                db.flush()
            added += 1
        except IntegrityError:
            # Another sync or a manual entry may win the unique source/reference race.
            if not db.scalar(select(Receipt.id).where((Receipt.source_key == row.source_key) | ((Receipt.channel == row.channel) & (Receipt.reference == row.reference)))):
                raise
    return added
