from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.static_url import public_static_path, public_static_url
from app.db.session import get_db
from app.models import PricingRule, Reservation, Seat, Store, Zone
from app.schemas.common import ResponseModel
from app.schemas.store import PricingItem, SeatItem, StoreDetail, StoreListItem
from app.services.business import calc_distance, find_busy_seat_ids, get_seat_status
from app.services.store_seat_maps import (
    get_published_map,
    is_image_mode,
    list_bookable_seats,
    map_summary,
)

router = APIRouter(prefix="/store", tags=["门店"])


def _normalize_cover_images(images: list | None) -> list | None:
    if not images:
        return images
    out = []
    for item in images:
        if not item:
            continue
        path = public_static_path(str(item))
        out.append(path or str(item))
    return out or None


def _store_list_item(store: Store, **extra) -> StoreListItem:
    item = StoreListItem.model_validate(store)
    item.cover_images = _normalize_cover_images(item.cover_images)
    for key, value in extra.items():
        setattr(item, key, value)
    return item


def _store_detail(store: Store) -> StoreDetail:
    item = StoreDetail.model_validate(store)
    item.cover_images = _normalize_cover_images(item.cover_images)
    return item


class AvailabilityQuery(BaseModel):
    start_time: datetime
    end_time: datetime


@router.get("/{store_id}/seat-map", response_model=ResponseModel)
def get_store_seat_map(store_id: int, db: Session = Depends(get_db)):
    store = db.get(Store, store_id)
    if not store or store.status != 1:
        raise HTTPException(status_code=404, detail="门店不存在")
    if not is_image_mode(store):
        return ResponseModel(data={"mode": "legacy", "store_id": store_id})

    published = get_published_map(db, store_id)
    if not published or not published.image_path or not published.markers:
        return ResponseModel(
            data={
                "mode": "image",
                "store_id": store_id,
                "published": False,
                "image_url": None,
                "aspect_ratio": None,
                "markers": [],
            }
        )
    summary = map_summary(published) or {}
    seat_ids = [int(m["seat_id"]) for m in (published.markers or []) if m.get("seat_id") is not None]
    seats = {
        s.id: s
        for s in db.scalars(select(Seat).where(Seat.id.in_(seat_ids))).all()
        if s.store_id == store_id
    }
    zones = {
        z.id: z.name
        for z in db.scalars(select(Zone).where(Zone.store_id == store_id)).all()
    }
    markers = []
    for m in published.markers or []:
        seat = seats.get(int(m["seat_id"]))
        if not seat or seat.status != 1:
            continue
        markers.append(
            {
                "seat_id": seat.id,
                "seat_code": seat.seat_code,
                "zone_id": seat.zone_id,
                "zone_name": zones.get(seat.zone_id) or "",
                "x_pct": m.get("x_pct"),
                "y_pct": m.get("y_pct"),
                "orient": m.get("orient") or "up",
                "has_outlet": seat.has_outlet,
                "has_curtain": seat.has_curtain,
                "seat_type": seat.seat_type,
            }
        )
    return ResponseModel(
        data={
            "mode": "image",
            "store_id": store_id,
            "published": True,
            "image_url": public_static_url(summary.get("image_path")),
            "aspect_ratio": summary.get("aspect_ratio"),
            "markers": markers,
        }
    )


@router.get("/{store_id}/availability", response_model=ResponseModel[list[SeatItem]])
def get_availability(
    store_id: int,
    start_time: datetime = Query(...),
    end_time: datetime = Query(...),
    db: Session = Depends(get_db),
):
    store = db.get(Store, store_id)
    if not store:
        raise HTTPException(status_code=404, detail="门店不存在")
    seats = list_bookable_seats(db, store)
    busy_ids = find_busy_seat_ids(db, [s.id for s in seats], start_time, end_time)
    items = []
    for s in seats:
        status = "occupied" if s.id in busy_ids else "available"
        items.append(
            SeatItem(
                id=s.id,
                seat_code=s.seat_code,
                zone_id=s.zone_id,
                seat_type=s.seat_type,
                has_outlet=s.has_outlet,
                has_curtain=s.has_curtain,
                pos_x=s.pos_x,
                pos_y=s.pos_y,
                status=status,
            )
        )
    return ResponseModel(data=items)


@router.get("/{store_id}/zones", response_model=ResponseModel)
def get_zones(store_id: int, db: Session = Depends(get_db)):
    zones = db.scalars(select(Zone).where(Zone.store_id == store_id).order_by(Zone.sort_order)).all()
    return ResponseModel(
        data=[{"id": z.id, "name": z.name, "type": z.type} for z in zones]
    )

@router.get("/list", response_model=ResponseModel[list[StoreListItem]])
def list_stores(
    latitude: float | None = Query(None),
    longitude: float | None = Query(None),
    db: Session = Depends(get_db),
):
    stores = db.scalars(select(Store).where(Store.status == 1)).all()
    items: list[StoreListItem] = []
    for store in stores:
        distance = None
        if latitude and longitude and store.latitude and store.longitude:
            distance = calc_distance(
                latitude, longitude, float(store.latitude), float(store.longitude)
            )
        items.append(_store_list_item(store, distance=distance))
    if latitude and longitude:
        items.sort(key=lambda x: x.distance if x.distance is not None else 99999)
    return ResponseModel(data=items)


@router.get("/{store_id}", response_model=ResponseModel[StoreDetail])
def get_store(store_id: int, db: Session = Depends(get_db)):
    store = db.get(Store, store_id)
    if not store or store.status != 1:
        raise HTTPException(status_code=404, detail="门店不存在")
    return ResponseModel(data=_store_detail(store))


@router.get("/{store_id}/seats", response_model=ResponseModel[list[SeatItem]])
def get_seats(store_id: int, db: Session = Depends(get_db)):
    store = db.get(Store, store_id)
    if not store:
        raise HTTPException(status_code=404, detail="门店不存在")
    seats = list_bookable_seats(db, store)
    now = datetime.now()
    items = [
        SeatItem(
            id=s.id,
            seat_code=s.seat_code,
            zone_id=s.zone_id,
            seat_type=s.seat_type,
            has_outlet=s.has_outlet,
            has_curtain=s.has_curtain,
            pos_x=s.pos_x,
            pos_y=s.pos_y,
            status=get_seat_status(db, s.id, now),
        )
        for s in seats
    ]
    return ResponseModel(data=items)


@router.get("/{store_id}/pricing", response_model=ResponseModel[list[PricingItem]])
def get_pricing(store_id: int, db: Session = Depends(get_db)):
    rules = db.scalars(
        select(PricingRule).where(PricingRule.store_id == store_id, PricingRule.is_active == 1)
        .order_by(PricingRule.sort_order)
    ).all()
    return ResponseModel(data=[PricingItem.model_validate(r) for r in rules])
