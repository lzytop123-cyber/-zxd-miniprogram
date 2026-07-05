"""门店标准座位布局：平面图 1–27 号，三区（标准 / 工位 / 沉浸）。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Seat, Store, Zone

PLAN_SEAT_COUNT = 27

# slot, zone_name, seat_type, has_curtain, left%, top%（与 miniprogram/utils/seat-layout.js 一致）
SEAT_LAYOUT: list[tuple[int, str, str, int, float, float]] = [
    (1, "标准区", "standard", 1, 81.51, 77.45),
    (2, "标准区", "standard", 1, 89.73, 77.45),
    (3, "标准区", "standard", 0, 90.06, 57.93),
    (4, "标准区", "standard", 0, 90.06, 49.44),
    (5, "标准区", "standard", 0, 90.06, 40.95),
    (6, "标准区", "standard", 0, 90.06, 32.46),
    (7, "标准区", "standard", 0, 90.06, 23.97),
    (8, "标准区", "standard", 0, 90.06, 15.48),
    (9, "标准区", "standard", 0, 64.85, 15.48),
    (10, "标准区", "standard", 0, 64.85, 23.97),
    (11, "标准区", "standard", 1, 64.85, 32.46),
    (12, "标准区", "standard", 1, 64.85, 58.35),
    (13, "标准区", "standard", 1, 64.85, 66.84),
    (14, "工位区", "window", 0, 55.75, 23.97),
    (15, "工位区", "window", 0, 55.75, 15.48),
    (16, "工位区", "window", 0, 37.45, 15.48),
    (17, "工位区", "window", 0, 37.45, 23.97),
    (18, "工位区", "window", 0, 37.45, 32.46),
    (19, "沉浸区", "standard", 0, 28.68, 23.97),
    (20, "沉浸区", "standard", 0, 28.68, 15.48),
    (21, "沉浸区", "standard", 0, 10.26, 15.48),
    (22, "沉浸区", "standard", 0, 10.26, 23.97),
    (23, "沉浸区", "standard", 0, 10.26, 32.46),
    (24, "沉浸区", "standard", 0, 10.26, 40.95),
    (25, "沉浸区", "standard", 1, 10.26, 85.5),
    (26, "沉浸区", "standard", 1, 10.26, 73.5),
    (27, "沉浸区", "standard", 1, 10.26, 61.5),
]

ZONE_ORDER = {"标准区": 0, "工位区": 1, "沉浸区": 2}

SLOT_ZONE: dict[int, str] = {slot: zone_name for slot, zone_name, *_ in SEAT_LAYOUT}


def zone_name_by_slot(slot: int | None) -> str | None:
    if not slot:
        return None
    return SLOT_ZONE.get(slot)

# 历史 A01/B08/D01 等 → 平面图号
LEGACY_CODE_TO_SLOT: dict[str, int] = {
    "C01": 1, "C02": 2, "A01": 3, "A02": 4, "A03": 5, "A04": 6,
    "A05": 7, "A06": 8, "A07": 9, "A08": 10, "C03": 11, "C04": 12,
    "C05": 13, "B01": 14, "B02": 15, "B03": 16, "B04": 17, "B05": 18,
    "B06": 19, "B07": 20, "B08": 21, "A09": 22, "B09": 23, "C09": 24,
    "D01": 22, "D02": 23, "D03": 24, "D1": 22, "D2": 23, "D3": 24,
    "C06": 25, "C07": 26, "C08": 27,
}

EXPECTED_SEAT_COUNT = PLAN_SEAT_COUNT


def expected_seat_codes() -> list[str]:
    return [str(i) for i in range(1, PLAN_SEAT_COUNT + 1)]


def seat_code_to_slot(seat_code: str | None) -> int | None:
    if not seat_code:
        return None
    code = str(seat_code).strip().upper()
    if code in LEGACY_CODE_TO_SLOT:
        return LEGACY_CODE_TO_SLOT[code]
    try:
        slot = int(code)
    except ValueError:
        return None
    if 1 <= slot <= PLAN_SEAT_COUNT:
        return slot
    return None


def _layout_pos(left_pct: float, top_pct: float) -> tuple[int, int]:
    """与小程序 900×700 画布对应，供后台平面图预览。"""
    return int(left_pct * 9), int(top_pct * 7)


def _sort_seats(seats: list[Seat]) -> list[Seat]:
    return sorted(seats, key=lambda s: seat_code_to_slot(s.seat_code) or 9999)


def ensure_store_seats(db: Session, store: Store) -> int:
    """补全门店 1–27 号座位（已有则同步区域与坐标）。"""
    zones: dict[str, Zone] = {}
    for zone_name in ZONE_ORDER:
        zone = db.scalar(select(Zone).where(Zone.store_id == store.id, Zone.name == zone_name))
        if not zone:
            zone = Zone(
                store_id=store.id,
                name=zone_name,
                type="window" if zone_name == "工位区" else "standard",
                sort_order=ZONE_ORDER[zone_name],
            )
            db.add(zone)
            db.flush()
        zones[zone_name] = zone

    existing = {
        s.seat_code: s
        for s in db.scalars(select(Seat).where(Seat.store_id == store.id, Seat.is_buffer == 0)).all()
    }
    added = 0

    for slot, zone_name, seat_type, has_curtain, left_pct, top_pct in SEAT_LAYOUT:
        code = str(slot)
        pos_x, pos_y = _layout_pos(left_pct, top_pct)
        zone = zones[zone_name]
        seat = existing.get(code)
        if seat:
            seat.zone_id = zone.id
            seat.seat_type = seat_type
            seat.has_curtain = has_curtain
            seat.pos_x = pos_x
            seat.pos_y = pos_y
            seat.status = 1
            continue
        db.add(
            Seat(
                store_id=store.id,
                zone_id=zone.id,
                seat_code=code,
                seat_type=seat_type,
                has_outlet=1,
                has_curtain=has_curtain,
                pos_x=pos_x,
                pos_y=pos_y,
            )
        )
        added += 1

    return added


def migrate_store_seat_codes(db: Session, store: Store) -> dict:
    """将历史 A01/B08 等编号迁移为 1–27，并补全缺失座位。"""
    seats = list(
        db.scalars(select(Seat).where(Seat.store_id == store.id, Seat.is_buffer == 0)).all()
    )
    pending: list[tuple[Seat, str]] = []
    for seat in seats:
        slot = seat_code_to_slot(seat.seat_code)
        if slot is None:
            continue
        target = str(slot)
        if seat.seat_code == target:
            continue
        pending.append((seat, target))

    for seat, _ in pending:
        seat.seat_code = f"__tmp_{seat.id}"
    db.flush()

    renamed = 0
    for seat, target in pending:
        seat.seat_code = target
        renamed += 1

    added = ensure_store_seats(db, store)
    return {"renamed": renamed, "added": added}


def store_seat_summary(db: Session, store_id: int) -> dict:
    store = db.get(Store, store_id)
    if not store:
        raise ValueError("门店不存在")

    seats = _sort_seats(
        list(
            db.scalars(
                select(Seat).where(Seat.store_id == store_id, Seat.is_buffer == 0)
            ).all()
        )
    )
    codes = {s.seat_code for s in seats}
    expected = expected_seat_codes()
    missing = [c for c in expected if c not in codes]
    enabled = sum(1 for s in seats if s.status == 1)

    return {
        "store_id": store_id,
        "store_name": store.name,
        "expected_count": EXPECTED_SEAT_COUNT,
        "actual_count": len(seats),
        "enabled_count": enabled,
        "missing_codes": missing,
        "is_complete": len(missing) == 0,
    }
