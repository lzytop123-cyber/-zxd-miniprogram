"""团购映射模板导入。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.data.deal_templates import DEAL_MAPPING_TEMPLATES
from app.models import MeituanDealMapping, Store


def list_deal_templates() -> list[dict]:
    return [
        {
            "deal_id": deal_id,
            "deal_name": name,
            "reward_type": reward_type.value,
            "reward_value": value,
        }
        for deal_id, name, reward_type, value, _, _ in DEAL_MAPPING_TEMPLATES
    ]


def import_deal_templates(
    db: Session,
    store_id: int,
    *,
    platform: int = 1,
    overwrite: bool = False,
) -> dict:
    store = db.get(Store, store_id)
    if not store:
        raise ValueError("门店不存在")

    added = 0
    updated = 0
    skipped = 0
    for deal_id, name, reward_type, value, ns, ne in DEAL_MAPPING_TEMPLATES:
        row = db.scalar(select(MeituanDealMapping).where(MeituanDealMapping.deal_id == deal_id))
        if row:
            if overwrite:
                row.store_id = store_id
                row.deal_name = name
                row.reward_type = reward_type
                row.reward_value = value
                row.night_start = ns
                row.night_end = ne
                row.platform = platform
                row.is_active = 1
                updated += 1
            else:
                skipped += 1
            continue
        db.add(
            MeituanDealMapping(
                store_id=store_id,
                deal_id=deal_id,
                deal_name=name,
                reward_type=reward_type,
                reward_value=value,
                night_start=ns,
                night_end=ne,
                platform=platform,
                is_active=1,
            )
        )
        added += 1
    return {"added": added, "updated": updated, "skipped": skipped, "total_templates": len(DEAL_MAPPING_TEMPLATES)}
