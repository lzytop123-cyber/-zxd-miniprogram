"""把未写门店的历史核销和收款记到千峰南路。

理工大店（store id 2）于 2026-11-13 下午才开业。在此之前没有 store_id 的
已核销/已退款团购订单，以及仍然无法按订单归属的收款（手工登记、充值、
订单门店为空的核销），归到 store id 1。已经写上门店的行一律不改。

只填补空值，可重复执行。不在这里提交事务。
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CardPurchaseOrder, MeituanOrder, MeituanOrderStatus, Reservation, Store
from app.models.receipts import Receipt

LEGACY_STORE_ID = 1
REDEEMED = (MeituanOrderStatus.verified, MeituanOrderStatus.refunded)


def backfill_receipt_stores(db: Session) -> dict:
    store = db.get(Store, LEGACY_STORE_ID)
    if store is None:
        raise RuntimeError(f"门店 {LEGACY_STORE_ID} 不存在，已中止，未写入任何门店归属")

    orders_assigned = 0
    pending_orders = db.scalars(
        select(MeituanOrder).where(
            MeituanOrder.store_id.is_(None),
            MeituanOrder.status.in_(REDEEMED),
        )
    ).all()
    for order in pending_orders:
        order.store_id = LEGACY_STORE_ID
        orders_assigned += 1
    db.flush()

    store_by_key = _store_by_source_key(db)
    receipts_from_orders = 0
    receipts_legacy = 0
    for receipt in db.scalars(select(Receipt).where(Receipt.store_id.is_(None))).all():
        # 先按订单上的门店（含刚补上的千峰南路，以及原本就是理工大店的订单）。
        store_id = store_by_key.get(receipt.source_key)
        if store_id:
            receipt.store_id = store_id
            receipts_from_orders += 1
        else:
            receipt.store_id = LEGACY_STORE_ID
            receipts_legacy += 1
    db.flush()
    return {
        "legacy_store_id": LEGACY_STORE_ID,
        "legacy_store_name": store.name,
        "orders_assigned": orders_assigned,
        "receipts_from_orders": receipts_from_orders,
        "receipts_legacy": receipts_legacy,
    }


def _store_by_source_key(db: Session) -> dict[str, int]:
    mapping: dict[str, int] = {}
    for order_id, store_id in db.execute(
        select(MeituanOrder.id, MeituanOrder.store_id).where(MeituanOrder.store_id.is_not(None))
    ):
        mapping[f"platform:{order_id}"] = int(store_id)
    for order_no, store_id in db.execute(
        select(Reservation.order_no, Reservation.store_id).where(Reservation.store_id.is_not(None))
    ):
        mapping[f"reservation:{order_no}"] = int(store_id)
    for order_no, store_id in db.execute(
        select(CardPurchaseOrder.order_no, CardPurchaseOrder.store_id).where(CardPurchaseOrder.store_id.is_not(None))
    ):
        mapping[f"card:{order_no}"] = int(store_id)
    return mapping
