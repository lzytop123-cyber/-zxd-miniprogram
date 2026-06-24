from datetime import time
from decimal import Decimal

from pydantic import BaseModel, Field


class StoreListItem(BaseModel):
    id: int
    name: str
    address: str | None = None
    latitude: Decimal | None = None
    longitude: Decimal | None = None
    cover_images: list | None = None
    distance: float | None = None
    status: int

    model_config = {"from_attributes": True}


class StoreDetail(StoreListItem):
    open_time: time | None = None
    close_time: time | None = None
    floor_plan: str | None = None
    wifi_name: str | None = None
    wifi_password: str | None = None


class SeatItem(BaseModel):
    id: int
    seat_code: str
    zone_id: int
    seat_type: str | None = None
    has_outlet: int
    has_curtain: int
    pos_x: int | None = None
    pos_y: int | None = None
    status: str

    model_config = {"from_attributes": True}


class PricingItem(BaseModel):
    id: int
    bill_type: str
    seat_type: str
    price: Decimal
    min_hours: int | None = None
    max_hours: int | None = None
    night_start: time | None = None
    night_end: time | None = None
    valid_days: int | None = None
    remark: str | None = None

    model_config = {"from_attributes": True}
