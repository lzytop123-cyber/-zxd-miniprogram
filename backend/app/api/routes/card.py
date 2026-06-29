from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.prod import block_mock_in_production
from app.db.session import get_db
from app.models import BillType, CardPurchaseOrder, PayType, PeriodCard, PricingRule, Store, User
from app.schemas.common import ResponseModel
from app.services.booking import add_wallet_log
from app.services.card_service import (
    BILL_TYPE_LABELS,
    PURCHASABLE_BILL_TYPES,
    fulfill_card_purchase,
)
from app.services.wechat_pay import WechatPayService

router = APIRouter(prefix="/card", tags=["期限卡"])


class CardPackageItem(BaseModel):
    bill_type: str
    label: str
    price: float
    remark: str | None = None
    valid_days: int | None = None
    session_count: int | None = None
    pricing_rule_id: int


class CardPurchaseRequest(BaseModel):
    store_id: int
    bill_type: BillType
    pay_type: PayType = PayType.wechat


def _session_count(rule: PricingRule) -> int | None:
    if rule.bill_type != BillType.session:
        return None
    return rule.valid_days or 10


def _package_item(rule: PricingRule) -> dict:
    label = BILL_TYPE_LABELS.get(rule.bill_type, rule.bill_type.value)
    return {
        "bill_type": rule.bill_type.value,
        "label": label,
        "price": float(rule.price),
        "remark": rule.remark,
        "valid_days": rule.valid_days,
        "session_count": _session_count(rule),
        "pricing_rule_id": rule.id,
    }


@router.get("/packages", response_model=ResponseModel)
def list_card_packages(
    store_id: int = Query(...),
    db: Session = Depends(get_db),
):
    store = db.get(Store, store_id)
    if not store or store.status != 1:
        raise HTTPException(status_code=404, detail="门店不存在")
    rules = db.scalars(
        select(PricingRule)
        .where(
            PricingRule.store_id == store_id,
            PricingRule.is_active == 1,
            PricingRule.bill_type.in_(list(PURCHASABLE_BILL_TYPES)),
        )
        .order_by(PricingRule.sort_order)
    ).all()
    return ResponseModel(
        data={
            "store_id": store_id,
            "store_name": store.name,
            "items": [_package_item(r) for r in rules],
        }
    )


@router.post("/purchase", response_model=ResponseModel)
def purchase_card(
    body: CardPurchaseRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if body.bill_type not in PURCHASABLE_BILL_TYPES:
        raise HTTPException(status_code=400, detail="该套餐不支持在线购买")
    store = db.get(Store, body.store_id)
    if not store or store.status != 1:
        raise HTTPException(status_code=404, detail="门店不存在")

    rule = db.scalar(
        select(PricingRule).where(
            PricingRule.store_id == body.store_id,
            PricingRule.bill_type == body.bill_type,
            PricingRule.is_active == 1,
        )
    )
    if not rule:
        raise HTTPException(status_code=404, detail="该门店暂无此套餐定价")

    amount = Decimal(str(rule.price))
    order_no = f"CRD{datetime.now().strftime('%Y%m%d%H%M%S')}{user.id}"
    order = CardPurchaseOrder(
        order_no=order_no,
        user_id=user.id,
        store_id=body.store_id,
        bill_type=body.bill_type,
        pricing_rule_id=rule.id,
        amount=amount,
        pay_type=body.pay_type,
        pay_status=0,
    )
    db.add(order)
    db.flush()

    label = BILL_TYPE_LABELS.get(body.bill_type, body.bill_type.value)
    description = f"知行岛{label}-{store.name}"

    if body.pay_type == PayType.balance:
        if user.balance < amount:
            raise HTTPException(status_code=400, detail="余额不足")
        try:
            add_wallet_log(db, user, "consume", amount, f"购买{label}", order_no)
        except ValueError:
            raise HTTPException(status_code=400, detail="余额不足")
        card = fulfill_card_purchase(db, order)
        db.commit()
        return ResponseModel(
            message="购买成功",
            data={
                "order_no": order_no,
                "pay_type": PayType.balance.value,
                "card_id": card.id,
                "card_name": card.card_name,
            },
        )

    if body.pay_type != PayType.wechat:
        raise HTTPException(status_code=400, detail="暂不支持该支付方式")

    pay_params = WechatPayService.create_jsapi_order(
        order_no,
        amount,
        user.openid,
        description,
        attach=f"card_purchase={order.id}",
    )
    db.commit()
    return ResponseModel(
        data={
            "order_no": order_no,
            "amount": float(amount),
            "pay_type": PayType.wechat.value,
            "wechat_pay": pay_params,
            "label": label,
        }
    )


@router.post("/purchase/{order_no}/mock", response_model=ResponseModel)
def mock_purchase_card(
    order_no: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    block_mock_in_production()
    order = db.scalar(
        select(CardPurchaseOrder).where(
            CardPurchaseOrder.order_no == order_no,
            CardPurchaseOrder.user_id == user.id,
        )
    )
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    if order.pay_status == 1:
        card = db.get(PeriodCard, order.period_card_id)
        return ResponseModel(
            message="已购买",
            data={"card_id": order.period_card_id, "card_name": card.card_name if card else None},
        )
    card = fulfill_card_purchase(db, order)
    db.commit()
    return ResponseModel(
        message="购买成功",
        data={"card_id": card.id, "card_name": card.card_name},
    )
