"""团购兑换默认门店配置。"""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import SiteExchangeSetting, Store


def get_or_create_exchange_setting(db: Session) -> SiteExchangeSetting:
    row = db.get(SiteExchangeSetting, 1)
    if row:
        return row
    row = SiteExchangeSetting(id=1, default_store_id=None)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def exchange_setting_dict(db: Session, row: SiteExchangeSetting) -> dict:
    store_name = None
    if row.default_store_id:
        store = db.get(Store, row.default_store_id)
        store_name = store.name if store else None
    return {
        "default_store_id": row.default_store_id,
        "default_store_name": store_name,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def resolve_exchange_store_id(db: Session, store_id: int | None) -> int:
    """兑换必须落到营业门店。

    优先级：请求显式 store_id → 后台默认门店（须营业）→ 唯一营业店 → 报错。
    """
    if store_id:
        return int(store_id)

    open_ids = list(
        db.scalars(select(Store.id).where(Store.status == 1).order_by(Store.id)).all()
    )
    if not open_ids:
        raise HTTPException(status_code=404, detail="暂无营业门店，请稍后再试")

    setting = db.get(SiteExchangeSetting, 1)
    default_id = int(setting.default_store_id) if setting and setting.default_store_id else None
    if default_id and default_id in open_ids:
        return default_id

    if len(open_ids) == 1:
        return int(open_ids[0])

    raise HTTPException(status_code=400, detail="请选择门店后再兑换")
