from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel

from app.models import BillType, PayType


class ReservationPreviewRequest(BaseModel):
    store_id: int
    bill_type: BillType = BillType.hourly
    start_time: datetime
    end_time: datetime | None = None
    seat_id: int | None = None
    coupon_id: int | None = None


class ReservationPreviewResponse(BaseModel):
    store_id: int
    seat_id: int | None = None
    seat_code: str | None = None
    bill_type: BillType
    start_time: datetime
    end_time: datetime
    duration_hours: Decimal
    original_price: Decimal
    discount_price: Decimal = Decimal("0.00")
    final_price: Decimal


class ReservationCreateRequest(BaseModel):
    store_id: int
    bill_type: BillType = BillType.hourly
    start_time: datetime
    end_time: datetime | None = None
    seat_id: int | None = None
    coupon_id: int | None = None


class ReservationPayRequest(BaseModel):
    order_no: str
    pay_type: PayType = PayType.wechat
    period_card_id: int | None = None
    coupon_id: int | None = None


class ReservationItem(BaseModel):
    id: int
    order_no: str
    store_id: int
    seat_id: int
    seat_code: str | None = None
    store_name: str | None = None
    bill_type: BillType
    start_time: datetime
    end_time: datetime
    final_price: Decimal | None = None
    pay_status: int
    status: int
    check_in_time: datetime | None = None
    created_at: datetime
    status_label: str | None = None
    status_hint: str | None = None

    model_config = {"from_attributes": True}


class WechatPayParams(BaseModel):
    timeStamp: str
    nonceStr: str
    package: str
    signType: str = "RSA"
    paySign: str


class ReservationPayResponse(BaseModel):
    order_no: str
    pay_type: PayType
    wechat_pay: WechatPayParams | None = None
