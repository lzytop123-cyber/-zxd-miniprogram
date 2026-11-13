"""按门店配置的图片座位图：草稿、发布、恢复与可订座位集合。"""

from __future__ import annotations

import math
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Seat, Store, StoreSeatMap, Zone

VALID_ORIENTS = frozenset({"up", "down", "left", "right", "n", "s", "e", "w"})
UPLOADS_DIR = Path(__file__).resolve().parents[2] / "uploads"


class SeatMapError(ValueError):
    pass


def is_image_mode(store: Store | None) -> bool:
    return bool(store) and getattr(store, "seat_map_mode", "legacy") == "image"


def get_draft_map(db: Session, store_id: int) -> StoreSeatMap | None:
    return db.scalar(
        select(StoreSeatMap)
        .where(StoreSeatMap.store_id == store_id, StoreSeatMap.state == "draft")
        .order_by(StoreSeatMap.version.desc(), StoreSeatMap.id.desc())
    )


def get_published_map(db: Session, store_id: int) -> StoreSeatMap | None:
    return db.scalar(
        select(StoreSeatMap)
        .where(StoreSeatMap.store_id == store_id, StoreSeatMap.state == "published")
        .order_by(StoreSeatMap.version.desc(), StoreSeatMap.id.desc())
    )


def list_archived_maps(db: Session, store_id: int, *, limit: int = 10) -> list[StoreSeatMap]:
    return list(
        db.scalars(
            select(StoreSeatMap)
            .where(StoreSeatMap.store_id == store_id, StoreSeatMap.state == "archived")
            .order_by(StoreSeatMap.version.desc(), StoreSeatMap.id.desc())
            .limit(limit)
        ).all()
    )


def published_image_seat_ids(db: Session, store_id: int) -> set[int]:
    pub = get_published_map(db, store_id)
    if not pub or not pub.markers:
        return set()
    ids: set[int] = set()
    for m in pub.markers:
        try:
            sid = int(m.get("seat_id"))
        except (TypeError, ValueError, AttributeError):
            continue
        ids.add(sid)
    return ids


def _next_version(db: Session, store_id: int) -> int:
    rows = db.scalars(select(StoreSeatMap.version).where(StoreSeatMap.store_id == store_id)).all()
    return (max(rows) if rows else 0) + 1


def _normalize_markers(db: Session, store_id: int, markers: list | None) -> list[dict]:
    if markers is None:
        return []
    if not isinstance(markers, list):
        raise SeatMapError("标记格式无效")
    seen: set[int] = set()
    out: list[dict] = []
    for raw in markers:
        if not isinstance(raw, dict):
            raise SeatMapError("标记格式无效")
        try:
            seat_id = int(raw.get("seat_id"))
            x_pct = float(raw.get("x_pct"))
            y_pct = float(raw.get("y_pct"))
        except (TypeError, ValueError):
            raise SeatMapError("标记缺少有效 seat_id/x_pct/y_pct") from None
        if seat_id in seen:
            raise SeatMapError(f"座位标记重复: {seat_id}")
        seen.add(seat_id)
        if not (0 <= x_pct <= 100 and 0 <= y_pct <= 100):
            raise SeatMapError("座位坐标须在 0–100% 内")
        orient = str(raw.get("orient") or "up").lower()
        if orient not in VALID_ORIENTS:
            raise SeatMapError(f"无效朝向: {orient}")
        seat = db.get(Seat, seat_id)
        if not seat or seat.store_id != store_id or seat.is_buffer:
            raise SeatMapError(f"座位不属于本店: {seat_id}")
        out.append(
            {
                "seat_id": seat_id,
                "x_pct": round(x_pct, 4),
                "y_pct": round(y_pct, 4),
                "orient": orient,
            }
        )
    return out


def _assert_image_path(image_path: str | None) -> str:
    if not image_path:
        raise SeatMapError("请先上传平面图")
    path = str(image_path).strip()
    if not path.startswith("/static/"):
        raise SeatMapError("图片路径无效")
    rel = path[len("/static/") :]
    full = UPLOADS_DIR / rel
    if not full.is_file():
        raise SeatMapError("平面图文件不存在")
    return path


def _assert_aspect(aspect_ratio) -> Decimal:
    try:
        ratio = Decimal(str(aspect_ratio))
    except Exception as exc:
        raise SeatMapError("画布比例无效") from exc
    if not math.isfinite(float(ratio)) or ratio <= 0:
        raise SeatMapError("画布比例须为正数")
    return ratio


def save_draft_map(
    db: Session,
    store_id: int,
    *,
    image_path: str | None,
    aspect_ratio,
    markers: list | None,
) -> StoreSeatMap:
    store = db.get(Store, store_id)
    if not store:
        raise SeatMapError("门店不存在")
    if not is_image_mode(store):
        raise SeatMapError("该门店为固定布局，不能编辑图片座位图")

    path = _assert_image_path(image_path)
    ratio = _assert_aspect(aspect_ratio)
    normalized = _normalize_markers(db, store_id, markers)

    draft = get_draft_map(db, store_id)
    if draft:
        draft.image_path = path
        draft.aspect_ratio = ratio
        draft.markers = normalized
        return draft

    draft = StoreSeatMap(
        store_id=store_id,
        version=_next_version(db, store_id),
        state="draft",
        image_path=path,
        aspect_ratio=ratio,
        markers=normalized,
    )
    db.add(draft)
    db.flush()
    return draft


def publish_draft_map(db: Session, store_id: int, *, require_all_enabled: bool = False) -> StoreSeatMap:
    store = db.get(Store, store_id)
    if not store:
        raise SeatMapError("门店不存在")
    if not is_image_mode(store):
        raise SeatMapError("该门店为固定布局，不能发布图片座位图")

    # 锁定门店行，避免并发发布
    db.execute(select(Store).where(Store.id == store_id).with_for_update())
    draft = get_draft_map(db, store_id)
    if not draft:
        raise SeatMapError("没有可发布的草稿")
    path = _assert_image_path(draft.image_path)
    _assert_aspect(draft.aspect_ratio)
    markers = _normalize_markers(db, store_id, draft.markers or [])
    if not markers:
        raise SeatMapError("发布前至少标注一个座位")
    if require_all_enabled:
        marked_ids = {marker["seat_id"] for marker in markers}
        enabled = db.scalars(select(Seat).where(
            Seat.store_id == store_id, Seat.status == 1, Seat.is_buffer == 0
        ).order_by(Seat.id))
        missing = [seat.seat_code for seat in enabled if seat.id not in marked_ids]
        if missing:
            raise SeatMapError(f"启用座位尚未标注：{'、'.join(missing)}")

    now = datetime.now()
    old = get_published_map(db, store_id)
    if old:
        old.state = "archived"

    draft.state = "published"
    draft.image_path = path
    draft.markers = markers
    draft.published_at = now
    store.floor_plan = path
    db.flush()
    return draft


def restore_map(db: Session, store_id: int, map_id: int) -> StoreSeatMap:
    store = db.get(Store, store_id)
    if not store:
        raise SeatMapError("门店不存在")
    if not is_image_mode(store):
        raise SeatMapError("该门店为固定布局")

    db.execute(select(Store).where(Store.id == store_id).with_for_update())
    source = db.get(StoreSeatMap, map_id)
    if not source or source.store_id != store_id:
        raise SeatMapError("座位图版本不存在")
    if source.state not in ("archived", "published"):
        raise SeatMapError("只能恢复已发布或归档版本")

    path = _assert_image_path(source.image_path)
    markers = _normalize_markers(db, store_id, source.markers or [])
    if not markers:
        raise SeatMapError("该版本没有座位标记")

    now = datetime.now()
    old = get_published_map(db, store_id)
    if old and old.id != source.id:
        old.state = "archived"

    # 从归档恢复时生成新的 published 版本，保留历史
    if source.state == "archived":
        published = StoreSeatMap(
            store_id=store_id,
            version=_next_version(db, store_id),
            state="published",
            image_path=path,
            aspect_ratio=source.aspect_ratio,
            markers=markers,
            published_at=now,
        )
        db.add(published)
        db.flush()
        store.floor_plan = path
        return published

    source.state = "published"
    source.published_at = now
    store.floor_plan = path
    db.flush()
    return source


def list_bookable_seats(db: Session, store: Store) -> list[Seat]:
    """顾客/预约可见的本店可订座位（不含停用、缓冲）。"""
    seats = list(
        db.scalars(
            select(Seat).where(Seat.store_id == store.id, Seat.is_buffer == 0, Seat.status == 1)
        ).all()
    )
    if not is_image_mode(store):
        from app.services.seat_setup import expected_seat_codes

        plan = set(expected_seat_codes())
        return [s for s in seats if s.seat_code in plan]

    allowed = published_image_seat_ids(db, store.id)
    if not allowed:
        return []
    return [s for s in seats if s.id in allowed]


def assert_seat_bookable(db: Session, store: Store, seat: Seat) -> None:
    if seat.store_id != store.id or seat.is_buffer or seat.status != 1:
        raise SeatMapError("座位不可用")
    if is_image_mode(store):
        if seat.id not in published_image_seat_ids(db, store.id):
            raise SeatMapError("座位未发布到本店座位图")
    else:
        from app.services.seat_setup import expected_seat_codes

        if seat.seat_code not in set(expected_seat_codes()):
            raise SeatMapError("座位不在平面图中")


def map_summary(row: StoreSeatMap | None, *, include_markers: bool = True) -> dict | None:
    if not row:
        return None
    data = {
        "id": row.id,
        "store_id": row.store_id,
        "version": row.version,
        "state": row.state,
        "image_path": row.image_path,
        "aspect_ratio": float(row.aspect_ratio) if row.aspect_ratio is not None else None,
        "marker_count": len(row.markers or []),
        "created_at": row.created_at.isoformat(sep=" ") if row.created_at else None,
        "published_at": row.published_at.isoformat(sep=" ") if row.published_at else None,
    }
    if include_markers:
        data["markers"] = row.markers or []
    return data


def zone_to_dict(z: Zone) -> dict:
    return {"id": z.id, "store_id": z.store_id, "name": z.name, "type": z.type, "sort_order": z.sort_order}
