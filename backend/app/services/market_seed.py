"""上岸集市分类种子数据。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import MarketCategory, MarketCategoryType

EXAM_CATEGORIES = [
    ("kaoyan", "考研", 10),
    ("kaogong", "考公", 20),
    ("kaozheng", "考证", 30),
    ("other", "其他", 40),
]

MATERIAL_CATEGORIES = [
    ("second_hand", "二手书", 10),
    ("notes", "原创笔记", 20),
    ("digital", "数字资料", 30),
    ("want", "求购", 40),
]

COPYRIGHT_TEXT_V1 = (
    "本人确认所发布内容为原创或已获得合法授权，不含盗版课程、侵权PDF或来源不明资料；"
    "平台仅展示信息并协助双方联系，不参与学员间付款与履约。"
)


def ensure_market_categories(db: Session) -> int:
    added = 0
    for code, name, sort_order in EXAM_CATEGORIES:
        row = db.scalar(
            select(MarketCategory).where(
                MarketCategory.type == MarketCategoryType.exam.value,
                MarketCategory.code == code,
            )
        )
        if row:
            row.name = name
            row.sort_order = sort_order
            row.status = 1
            continue
        db.add(
            MarketCategory(
                type=MarketCategoryType.exam.value,
                code=code,
                name=name,
                sort_order=sort_order,
                status=1,
            )
        )
        added += 1

    for code, name, sort_order in MATERIAL_CATEGORIES:
        row = db.scalar(
            select(MarketCategory).where(
                MarketCategory.type == MarketCategoryType.material.value,
                MarketCategory.code == code,
            )
        )
        if row:
            row.name = name
            row.sort_order = sort_order
            row.status = 1
            continue
        db.add(
            MarketCategory(
                type=MarketCategoryType.material.value,
                code=code,
                name=name,
                sort_order=sort_order,
                status=1,
            )
        )
        added += 1

    if added:
        db.commit()
    else:
        db.commit()
    return added
