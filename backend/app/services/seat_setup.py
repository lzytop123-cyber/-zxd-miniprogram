"""门店标准座位布局：补全 A/B/C 区 + D 区（平面图 22–24 号位）。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Seat, Store, Zone

SEAT_ZONE_SPECS = (
    ("A区", "A", "standard", 0, 40),
    ("B区", "B", "window", 1, 180),
    ("C区", "C", "standard", 2, 320),
)
SEATS_PER_ZONE = 8
EXTRA_SEAT_SPECS = (
    ("D区", "D", "standard", 3, (
        ("D01", 30, 400),
        ("D02", 30, 470),
        ("D03", 30, 540),
    )),
)
EXPECTED_SEAT_COUNT = SEATS_PER_ZONE * len(SEAT_ZONE_SPECS) + sum(len(s[4]) for s in EXTRA_SEAT_SPECS)


def expected_seat_codes() -> list[str]:
    codes: list[str] = []
    for _, prefix, _, _, _ in SEAT_ZONE_SPECS:
        for i in range(1, SEATS_PER_ZONE + 1):
            codes.append(f"{prefix}{i:02d}")
    for _, _, _, _, seats in EXTRA_SEAT_SPECS:
        for code, _, _ in seats:
            codes.append(code)
    return codes


def _seat_position(index: int, start_y: int) -> tuple[int, int]:
    col = (index - 1) % 4
    row = (index - 1) // 4
    return 30 + col * 90, start_y + row * 70


def ensure_store_seats(db: Session, store: Store) -> int:
    """补全门店座位（已有则跳过，可重复执行）。"""
    zones: dict[str, Zone] = {}
    for name, prefix, zone_type, sort_order, _ in SEAT_ZONE_SPECS:
        zone = db.scalar(select(Zone).where(Zone.store_id == store.id, Zone.name == name))
        if not zone:
            zone = Zone(store_id=store.id, name=name, type=zone_type, sort_order=sort_order)
            db.add(zone)
            db.flush()
        zones[prefix] = zone

    existing_codes = {
        s.seat_code
        for s in db.scalars(select(Seat).where(Seat.store_id == store.id, Seat.is_buffer == 0)).all()
    }
    added: list[Seat] = []
    for name, prefix, zone_type, _, start_y in SEAT_ZONE_SPECS:
        for i in range(1, SEATS_PER_ZONE + 1):
            code = f"{prefix}{i:02d}"
            if code in existing_codes:
                continue
            pos_x, pos_y = _seat_position(i, start_y)
            added.append(
                Seat(
                    store_id=store.id,
                    zone_id=zones[prefix].id,
                    seat_code=code,
                    seat_type=zone_type,
                    has_outlet=1,
                    has_curtain=1 if prefix == "C" else 0,
                    pos_x=pos_x,
                    pos_y=pos_y,
                )
            )
    if added:
        db.add_all(added)

    for name, prefix, zone_type, _, start_y in SEAT_ZONE_SPECS:
        for i in range(1, SEATS_PER_ZONE + 1):
            code = f"{prefix}{i:02d}"
            seat = db.scalar(select(Seat).where(Seat.store_id == store.id, Seat.seat_code == code))
            if not seat:
                continue
            pos_x, pos_y = _seat_position(i, start_y)
            seat.pos_x = pos_x
            seat.pos_y = pos_y
            seat.zone_id = zones[prefix].id
            seat.seat_type = zone_type

    extra_new = 0
    for zone_name, prefix, zone_type, sort_order, seats in EXTRA_SEAT_SPECS:
        zone = db.scalar(select(Zone).where(Zone.store_id == store.id, Zone.name == zone_name))
        if not zone:
            zone = Zone(store_id=store.id, name=zone_name, type=zone_type, sort_order=sort_order)
            db.add(zone)
            db.flush()
        for code, pos_x, pos_y in seats:
            if code in existing_codes:
                seat = db.scalar(select(Seat).where(Seat.store_id == store.id, Seat.seat_code == code))
                if seat:
                    seat.zone_id = zone.id
                    seat.seat_type = zone_type
                    seat.pos_x = pos_x
                    seat.pos_y = pos_y
                    seat.status = 1
                continue
            db.add(
                Seat(
                    store_id=store.id,
                    zone_id=zone.id,
                    seat_code=code,
                    seat_type=zone_type,
                    has_outlet=1,
                    has_curtain=0,
                    pos_x=pos_x,
                    pos_y=pos_y,
                )
            )
            extra_new += 1

    return len(added) + extra_new


def store_seat_summary(db: Session, store_id: int) -> dict:
    store = db.get(Store, store_id)
    if not store:
        raise ValueError("门店不存在")

    seats = db.scalars(
        select(Seat).where(Seat.store_id == store_id, Seat.is_buffer == 0).order_by(Seat.seat_code)
    ).all()
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
