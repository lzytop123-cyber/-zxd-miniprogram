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


_ROAD_SUFFIXES = ("南路", "北路", "东路", "西路", "中路", "路")


def store_name_aliases(name: str) -> list[str]:
    """从门店名抽出可在团购标题里出现的叫法。

    「知行岛自习室(千峰南路店)」→ 千峰南路店 / 千峰南路 / 千峰。
    「知行岛自习室(理工大店)」→ 理工大店 / 理工大。
    """
    raw = (name or "").strip()
    if not raw:
        return []
    cores: list[str] = []
    for left, right in (("（", "）"), ("(", ")")):
        if left in raw and right in raw:
            inner = raw.split(left, 1)[1].split(right, 1)[0].strip()
            if inner:
                cores.append(inner)
    if not cores:
        cores.append(raw)
    aliases: list[str] = []
    for core in cores:
        aliases.append(core)
        trimmed = core[:-1] if core.endswith("店") and len(core) > 2 else core
        if trimmed != core:
            aliases.append(trimmed)
        for suffix in _ROAD_SUFFIXES:
            if trimmed.endswith(suffix) and len(trimmed) > len(suffix) + 1:
                aliases.append(trimmed[: -len(suffix)])
                break
    out: list[str] = []
    for alias in aliases:
        if len(alias) >= 2 and alias not in out:
            out.append(alias)
    return out


def store_short_name(name: str) -> str:
    aliases = store_name_aliases(name)
    return aliases[0] if aliases else (name or "").strip()


def infer_store_from_deal_name(stores: list, deal_name: str):
    """商品名只命中一家店时返回该店；没命中或同时命中多家则不推断。"""
    title = (deal_name or "").strip()
    if not title:
        return None
    hits = []
    for store in stores:
        aliases = store_name_aliases(getattr(store, "name", "") or "")
        if any(alias in title for alias in aliases):
            hits.append(store)
    if len(hits) == 1:
        return hits[0]
    return None


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
