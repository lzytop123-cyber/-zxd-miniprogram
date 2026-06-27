from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.static_url import public_static_path
from app.db.session import get_db
from app.models import PricingRule, Reservation, Seat, Store, Zone
from app.schemas.common import ResponseModel
from app.schemas.store import PricingItem, SeatItem, StoreDetail, StoreListItem
from app.services.business import calc_distance, get_seat_status

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


@router.get("/{store_id}/availability", response_model=ResponseModel[list[SeatItem]])
def get_availability(
    store_id: int,
    start_time: datetime = Query(...),
    end_time: datetime = Query(...),
    db: Session = Depends(get_db),
):
    seats = db.scalars(
        select(Seat).where(Seat.store_id == store_id, Seat.is_buffer == 0, Seat.status == 1)
    ).all()
    items = []
    for s in seats:
        conflict = db.scalar(
            select(Reservation).where(
                Reservation.seat_id == s.id,
                Reservation.pay_status.in_([0, 1]),
                Reservation.status.in_([0, 1]),
                Reservation.end_time > datetime.now(),
                Reservation.start_time < end_time,
                Reservation.end_time > start_time,
            )
        )
        status = "occupied" if conflict else "available"
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
    seats = db.scalars(
        select(Seat).where(Seat.store_id == store_id, Seat.is_buffer == 0, Seat.status == 1)
    ).all()
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
