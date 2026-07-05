from datetime import date, datetime, time, timedelta
from decimal import Decimal
import uuid

from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin, get_current_user
from app.core.config import settings
from app.core.static_url import public_static_path, public_static_url
from app.core.security import create_access_token, hash_password, verify_password
from app.db.session import get_db
from app.models import (
    AdminUser,
    BillType,
    CardPurchaseOrder,
    CardType,
    Coupon,
    HomeBanner,
    HomeCarouselSetting,
    MeituanDealMapping,
    MeituanOrder,
    PendingDealMapping,
    PayType,
    PeriodCard,
    PointLog,
    PricingRule,
    Reservation,
    RewardType,
    Seat,
    Store,
    StudyStat,
    User,
    WalletLog,
    Zone,
)
from app.schemas.common import PageParams, PageResult, ResponseModel
from app.schemas.reservation import ReservationItem
from app.schemas.user import STUDY_GOAL_LABELS
from app.services import assistant as assistant_service
from app.services.admin_ops import (
    admin_force_checkout,
    admin_remote_unlock,
    issue_admin_period_card,
    period_card_admin_dict,
    update_admin_period_card,
    user_overview,
)
from app.services.booking import (
    add_wallet_log,
    auto_checkin_reservation,
    change_reservation_seat,
    finalize_expired_reservation,
    seat_options_for_change,
)
from app.services.card_service import refund_period_card_consume, repair_misissued_card_validity
from app.services.card_service import BILL_TYPE_LABELS
from app.services.deal_mapping_service import mark_pending_resolved_by_deal_id, resolve_pending_deal
from app.services.schema_migrate import get_last_migration_result, run_schema_migrations
from app.services.seat_setup import ensure_store_seats, migrate_store_seat_codes, seat_code_to_slot, store_seat_summary
from app.services.wechat_pay import WechatPayService

router = APIRouter(prefix="/admin", tags=["后台管理"])

BANNER_DIR = Path(__file__).resolve().parents[3] / "uploads" / "banners"
STORE_COVER_DIR = Path(__file__).resolve().parents[3] / "uploads" / "stores"
BANNER_IMAGE_TYPES = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/gif": "gif",
}


class AdminLoginRequest(BaseModel):
    username: str
    password: str


class AdminLoginResponse(BaseModel):
    token: str
    username: str


@router.post("/login", response_model=ResponseModel[AdminLoginResponse])
def admin_login(body: AdminLoginRequest, db: Session = Depends(get_db)):
    admin = db.scalar(select(AdminUser).where(AdminUser.username == body.username))
    if not admin or not verify_password(body.password, admin.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    token = create_access_token(f"admin:{admin.id}")
    return ResponseModel(data=AdminLoginResponse(token=token, username=admin.username))


@router.get("/system/coupon", response_model=ResponseModel)
def coupon_system_status(_: object = Depends(get_current_admin)):
    """检查云老板/美团核销配置（不暴露密钥）。"""
    from app.services.yunlaoban import _use_mock

    configured = bool(
        settings.yunlaoban_client_id and settings.yunlaoban_secret and settings.yunlaoban_shop_id
    )
    return ResponseModel(
        data={
            "coupon_provider": settings.coupon_provider,
            "yunlaoban_configured": configured,
            "use_mock": _use_mock(),
            "shop_id": settings.yunlaoban_shop_id or None,
            "base_url": settings.yunlaoban_base_url,
        }
    )


@router.get("/reservations", response_model=ResponseModel)
def admin_reservations(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    store_id: int | None = None,
    pay_status: int | None = None,
    status: int | None = None,
    order_no: str | None = None,
    user_id: int | None = None,
    _: object = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    query = select(Reservation)
    if store_id:
        query = query.where(Reservation.store_id == store_id)
    if pay_status is not None:
        query = query.where(Reservation.pay_status == pay_status)
    if status is not None:
        query = query.where(Reservation.status == status)
    if order_no:
        query = query.where(Reservation.order_no.contains(order_no.strip()))
    if user_id:
        query = query.where(Reservation.user_id == user_id)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.scalars(
        query.order_by(Reservation.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()

    _sync_reservation_rows_on_read(db, rows)

    items = []
    for r in rows:
        base = _reservation_admin_item(db, r)
        if base:
            items.append(base)

    return ResponseModel(
        data=PageResult(items=items, total=total or 0, page=page, page_size=page_size)
    )


@router.get("/stats", response_model=ResponseModel)
def admin_stats(_: object = Depends(get_current_admin), db: Session = Depends(get_db)):
    today = date.today()
    today_start = datetime.combine(today, datetime.min.time())
    today_end = datetime.combine(today, datetime.max.time())
    today_revenue = db.scalar(
        select(func.coalesce(func.sum(Reservation.final_price), 0)).where(
            Reservation.pay_status == 1,
            Reservation.created_at >= today_start,
            Reservation.created_at <= today_end,
        )
    )
    active_count = db.scalar(
        select(func.count()).where(Reservation.status == 1, Reservation.pay_status == 1)
    )
    store_count = db.scalar(select(func.count()).select_from(Store).where(Store.status == 1))
    total_seats = db.scalar(
        select(func.count()).select_from(Seat).where(Seat.is_buffer == 0, Seat.status == 1)
    )
    month_start = datetime.combine(today.replace(day=1), datetime.min.time())
    month_revenue = db.scalar(
        select(func.coalesce(func.sum(Reservation.final_price), 0)).where(
            Reservation.pay_status == 1,
            Reservation.created_at >= month_start,
        )
    )
    new_users = db.scalar(
        select(func.count()).select_from(User).where(User.created_at >= today_start)
    )
    occupancy = round((active_count or 0) / max(total_seats or 1, 1) * 100, 1)
    return ResponseModel(
        data={
            "today_revenue": float(today_revenue or 0),
            "month_revenue": float(month_revenue or 0),
            "active_users": active_count or 0,
            "store_count": store_count or 0,
            "total_seats": total_seats or 0,
            "occupancy_rate": occupancy,
            "new_users_today": new_users or 0,
        }
    )


@router.get("/stats/revenue", response_model=ResponseModel)
def revenue_stats(
    days: int = Query(7, ge=1, le=30),
    _: object = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    since = date.today() - timedelta(days=days - 1)
    rows = db.execute(
        select(
            func.date(Reservation.created_at).label("day"),
            func.coalesce(func.sum(Reservation.final_price), 0).label("revenue"),
            func.count().label("orders"),
        )
        .where(Reservation.pay_status == 1, Reservation.created_at >= datetime.combine(since, datetime.min.time()))
        .group_by(func.date(Reservation.created_at))
        .order_by(func.date(Reservation.created_at))
    ).all()
    return ResponseModel(
        data=[
            {"date": str(r.day), "revenue": float(r.revenue), "orders": r.orders}
            for r in rows
        ]
    )


class DealMappingItem(BaseModel):
    id: int
    store_id: int | None
    deal_id: str
    deal_name: str | None
    reward_type: str
    reward_value: int | None
    is_active: int

    model_config = {"from_attributes": True}


class DealMappingCreateRequest(BaseModel):
    store_id: int | None = None
    deal_id: str
    deal_name: str | None = None
    reward_type: RewardType
    reward_value: int | None = None
    platform: int = 1
    is_active: int = 1


class PendingDealResolveRequest(BaseModel):
    store_id: int | None = None
    deal_name: str | None = None
    reward_type: RewardType | None = None
    reward_value: int | None = None


class CouponCreateRequest(BaseModel):
    user_id: int
    coupon_name: str
    discount_type: str = "amount"
    discount_val: float
    min_amount: float = 0
    expire_days: int = 30


class AdminStoreItem(BaseModel):
    id: int
    name: str
    address: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    open_time: str | None = None
    close_time: str | None = None
    wifi_name: str | None = None
    wifi_password: str | None = None
    floor_plan: str | None = None
    cover_images: list[str] = []
    meituan_shop_id: str | None = None
    status: int

    model_config = {"from_attributes": True}


class AdminStoreUpdateRequest(BaseModel):
    name: str | None = None
    address: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    open_time: str | None = None
    close_time: str | None = None
    wifi_name: str | None = None
    wifi_password: str | None = None
    floor_plan: str | None = None
    cover_images: list[str] | None = None
    meituan_shop_id: str | None = None
    status: int | None = None


class AdminPricingCreateRequest(BaseModel):
    bill_type: BillType
    seat_type: str = "standard"
    price: float
    min_hours: int | None = None
    max_hours: int | None = None
    night_start: str | None = None
    night_end: str | None = None
    valid_days: int | None = None
    remark: str | None = None
    sort_order: int = 0
    is_active: int = 1


class AdminPricingUpdateRequest(BaseModel):
    price: float | None = None
    min_hours: int | None = None
    max_hours: int | None = None
    night_start: str | None = None
    night_end: str | None = None
    valid_days: int | None = None
    remark: str | None = None
    sort_order: int | None = None
    is_active: int | None = None


def _time_to_str(value: time | None) -> str | None:
    if value is None:
        return None
    return value.strftime("%H:%M")


def _parse_time(value: str | None) -> time | None:
    if value is None or value == "":
        return None
    parts = value.strip().split(":")
    if len(parts) < 2:
        raise ValueError("时间格式应为 HH:MM")
    return time(int(parts[0]), int(parts[1]), int(parts[2]) if len(parts) > 2 else 0)


def _cover_images_admin(store: Store) -> list[str]:
    if not store.cover_images:
        return []
    return [public_static_url(u) for u in store.cover_images if u]


def _cover_images_to_store(urls: list[str] | None) -> list | None:
    if urls is None:
        return None
    out: list[str] = []
    for url in urls:
        path = public_static_path(url)
        if path:
            out.append(path)
    return out


def _store_to_admin_item(store: Store) -> dict:
    return {
        "id": store.id,
        "name": store.name,
        "address": store.address,
        "latitude": float(store.latitude) if store.latitude is not None else None,
        "longitude": float(store.longitude) if store.longitude is not None else None,
        "open_time": _time_to_str(store.open_time),
        "close_time": _time_to_str(store.close_time),
        "wifi_name": store.wifi_name,
        "wifi_password": store.wifi_password,
        "floor_plan": store.floor_plan,
        "cover_images": _cover_images_admin(store),
        "meituan_shop_id": store.meituan_shop_id,
        "status": store.status,
    }


def _pricing_to_dict(rule: PricingRule) -> dict:
    return {
        "id": rule.id,
        "store_id": rule.store_id,
        "bill_type": rule.bill_type.value,
        "seat_type": rule.seat_type,
        "price": float(rule.price),
        "min_hours": rule.min_hours,
        "max_hours": rule.max_hours,
        "night_start": _time_to_str(rule.night_start),
        "night_end": _time_to_str(rule.night_end),
        "valid_days": rule.valid_days,
        "remark": rule.remark,
        "sort_order": rule.sort_order,
        "is_active": rule.is_active,
    }


@router.get("/deal-mappings", response_model=ResponseModel)
def list_deal_mappings(
    platform: int | None = Query(None, ge=1, le=2),
    _: object = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    query = select(MeituanDealMapping).order_by(MeituanDealMapping.id.desc())
    if platform is not None:
        query = query.where(MeituanDealMapping.platform == platform)
    rows = db.scalars(query).all()
    return ResponseModel(
        data=[
            {
                "id": r.id,
                "store_id": r.store_id,
                "deal_id": r.deal_id,
                "deal_name": r.deal_name,
                "reward_type": r.reward_type.value,
                "reward_value": r.reward_value,
                "platform": getattr(r, "platform", 1) or 1,
                "is_active": r.is_active,
            }
            for r in rows
        ]
    )


@router.post("/deal-mappings", response_model=ResponseModel)
def create_deal_mapping(
    body: DealMappingCreateRequest,
    _: object = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    row = MeituanDealMapping(
        store_id=body.store_id,
        deal_id=body.deal_id,
        deal_name=body.deal_name,
        reward_type=body.reward_type,
        reward_value=body.reward_value,
        platform=body.platform,
        is_active=body.is_active,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    mark_pending_resolved_by_deal_id(db, body.deal_id)
    return ResponseModel(message="已添加", data={"id": row.id})


@router.get("/deal-mappings/pending", response_model=ResponseModel)
def list_pending_deal_mappings(
    platform: int | None = Query(None, ge=1, le=2),
    _: object = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    query = select(PendingDealMapping).where(PendingDealMapping.status == "pending")
    if platform is not None:
        query = query.where(PendingDealMapping.platform == platform)
    rows = db.scalars(query.order_by(PendingDealMapping.updated_at.desc())).all()
    return ResponseModel(
        data=[
            {
                "id": r.id,
                "deal_id": r.deal_id,
                "deal_name": r.deal_name,
                "platform": r.platform,
                "last_coupon_code": r.last_coupon_code,
                "suggested_reward_type": r.suggested_reward_type.value if r.suggested_reward_type else None,
                "suggested_reward_value": r.suggested_reward_value,
                "hit_count": r.hit_count,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "updated_at": r.updated_at.isoformat() if r.updated_at else None,
            }
            for r in rows
        ]
    )


@router.post("/deal-mappings/pending/{pending_id}/resolve", response_model=ResponseModel)
def resolve_pending_deal_mapping(
    pending_id: int,
    body: PendingDealResolveRequest,
    _: object = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    pending = db.get(PendingDealMapping, pending_id)
    if not pending or pending.status != "pending":
        raise HTTPException(status_code=404, detail="待配置项不存在")
    try:
        mapping = resolve_pending_deal(
            db,
            pending_id,
            store_id=body.store_id,
            reward_type=body.reward_type or pending.suggested_reward_type or RewardType.day_pass,
            reward_value=body.reward_value if body.reward_value is not None else pending.suggested_reward_value,
            deal_name=body.deal_name or pending.deal_name,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return ResponseModel(
        message="已配置并生效",
        data={
            "id": mapping.id,
            "deal_id": mapping.deal_id,
            "deal_name": mapping.deal_name,
            "reward_type": mapping.reward_type.value,
            "reward_value": mapping.reward_value,
        },
    )


@router.post("/deal-mappings/pending/{pending_id}/dismiss", response_model=ResponseModel)
def dismiss_pending_deal_mapping(
    pending_id: int,
    _: object = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    pending = db.get(PendingDealMapping, pending_id)
    if not pending or pending.status != "pending":
        raise HTTPException(status_code=404, detail="待配置项不存在")
    pending.status = "dismissed"
    db.commit()
    return ResponseModel(message="已忽略")


@router.get("/coupons", response_model=ResponseModel)
def list_coupons(
    user_id: int | None = None,
    _: object = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    query = select(Coupon)
    if user_id:
        query = query.where(Coupon.user_id == user_id)
    rows = db.scalars(query.order_by(Coupon.id.desc()).limit(100)).all()
    return ResponseModel(
        data=[
            {
                "id": c.id,
                "user_id": c.user_id,
                "coupon_name": c.coupon_name,
                "discount_type": c.discount_type,
                "discount_val": float(c.discount_val or 0),
                "min_amount": float(c.min_amount or 0),
                "expire_date": str(c.expire_date) if c.expire_date else None,
                "status": c.status,
            }
            for c in rows
        ]
    )


@router.post("/coupons", response_model=ResponseModel)
def create_coupon(
    body: CouponCreateRequest,
    _: object = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    user = db.get(User, body.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    coupon = Coupon(
        user_id=body.user_id,
        coupon_name=body.coupon_name,
        discount_type=body.discount_type,
        discount_val=Decimal(str(body.discount_val)),
        min_amount=Decimal(str(body.min_amount)),
        expire_date=date.today() + timedelta(days=body.expire_days),
        status=0,
    )
    db.add(coupon)
    db.commit()
    db.refresh(coupon)
    return ResponseModel(message="已发放", data={"id": coupon.id})


@router.delete("/coupons/{coupon_id}", response_model=ResponseModel)
def delete_coupon(
    coupon_id: int,
    _: object = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    coupon = db.get(Coupon, coupon_id)
    if not coupon:
        raise HTTPException(status_code=404, detail="优惠券不存在")
    if coupon.status == 1:
        raise HTTPException(status_code=400, detail="已使用的优惠券不可删除")
    db.delete(coupon)
    db.commit()
    return ResponseModel(message="已删除")


@router.get("/seats", response_model=ResponseModel)
def list_seats(
    store_id: int = Query(1),
    _: object = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    zones = {
        z.id: z.name
        for z in db.scalars(select(Zone).where(Zone.store_id == store_id)).all()
    }
    seats = list(
        db.scalars(
            select(Seat).where(Seat.store_id == store_id, Seat.is_buffer == 0)
        ).all()
    )
    seats.sort(key=lambda s: seat_code_to_slot(s.seat_code) or 9999)
    return ResponseModel(
        data=[
            {
                "id": s.id,
                "seat_code": s.seat_code,
                "zone_name": zones.get(s.zone_id, "-"),
                "seat_type": s.seat_type,
                "has_outlet": s.has_outlet,
                "has_curtain": s.has_curtain,
                "pos_x": s.pos_x,
                "pos_y": s.pos_y,
                "status": s.status,
            }
            for s in seats
        ]
    )


@router.patch("/seats/{seat_id}/status", response_model=ResponseModel)
def update_seat_status(
    seat_id: int,
    status: int = Query(..., ge=0, le=1),
    _: object = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    seat = db.get(Seat, seat_id)
    if not seat:
        raise HTTPException(status_code=404, detail="座位不存在")
    seat.status = status
    db.commit()
    return ResponseModel(message="已更新")


@router.get("/stores/{store_id}/seats/summary", response_model=ResponseModel)
def admin_store_seats_summary(
    store_id: int,
    _: object = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    try:
        return ResponseModel(data=store_seat_summary(db, store_id))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/stores/{store_id}/ensure-seats", response_model=ResponseModel)
def admin_ensure_store_seats(
    store_id: int,
    _: object = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    store = db.get(Store, store_id)
    if not store:
        raise HTTPException(status_code=404, detail="门店不存在")
    result = migrate_store_seat_codes(db, store)
    db.commit()
    summary = store_seat_summary(db, store_id)
    return ResponseModel(
        message=f"已补全座位，迁移 {result['renamed']} 个、新增 {result['added']} 个",
        data={**summary, "added": result["added"], "renamed": result["renamed"]},
    )


@router.get("/stores", response_model=ResponseModel)
def list_stores_admin(_: object = Depends(get_current_admin), db: Session = Depends(get_db)):
    stores = db.scalars(select(Store).order_by(Store.id)).all()
    return ResponseModel(data=[_store_to_admin_item(s) for s in stores])


@router.get("/stores/{store_id}", response_model=ResponseModel)
def get_store_admin(
    store_id: int,
    _: object = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    store = db.get(Store, store_id)
    if not store:
        raise HTTPException(status_code=404, detail="门店不存在")
    return ResponseModel(data=_store_to_admin_item(store))


@router.put("/stores/{store_id}", response_model=ResponseModel)
def update_store_admin(
    store_id: int,
    body: AdminStoreUpdateRequest,
    _: object = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    store = db.get(Store, store_id)
    if not store:
        raise HTTPException(status_code=404, detail="门店不存在")

    data = body.model_dump(exclude_unset=True)
    for field in ("open_time", "close_time"):
        if field in data:
            try:
                data[field] = _parse_time(data[field])
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))
    if "cover_images" in data:
        data["cover_images"] = _cover_images_to_store(data["cover_images"])

    for key, value in data.items():
        if key in ("latitude", "longitude") and value is not None:
            setattr(store, key, Decimal(str(value)))
        else:
            setattr(store, key, value)

    db.commit()
    db.refresh(store)
    return ResponseModel(message="已保存", data=_store_to_admin_item(store))


@router.get("/stores/{store_id}/pricing", response_model=ResponseModel)
def list_store_pricing(
    store_id: int,
    _: object = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    store = db.get(Store, store_id)
    if not store:
        raise HTTPException(status_code=404, detail="门店不存在")
    rules = db.scalars(
        select(PricingRule)
        .where(PricingRule.store_id == store_id)
        .order_by(PricingRule.sort_order, PricingRule.id)
    ).all()
    return ResponseModel(data=[_pricing_to_dict(r) for r in rules])


@router.post("/stores/{store_id}/pricing", response_model=ResponseModel)
def create_store_pricing(
    store_id: int,
    body: AdminPricingCreateRequest,
    _: object = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    store = db.get(Store, store_id)
    if not store:
        raise HTTPException(status_code=404, detail="门店不存在")

    try:
        night_start = _parse_time(body.night_start)
        night_end = _parse_time(body.night_end)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    rule = PricingRule(
        store_id=store_id,
        bill_type=body.bill_type,
        seat_type=body.seat_type,
        price=Decimal(str(body.price)),
        min_hours=body.min_hours,
        max_hours=body.max_hours,
        night_start=night_start,
        night_end=night_end,
        valid_days=body.valid_days,
        remark=body.remark,
        sort_order=body.sort_order,
        is_active=body.is_active,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return ResponseModel(message="已添加", data=_pricing_to_dict(rule))


@router.patch("/pricing/{rule_id}", response_model=ResponseModel)
def update_pricing_rule(
    rule_id: int,
    body: AdminPricingUpdateRequest,
    _: object = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    rule = db.get(PricingRule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="价格规则不存在")

    data = body.model_dump(exclude_unset=True)
    for field in ("night_start", "night_end"):
        if field in data:
            try:
                data[field] = _parse_time(data[field])
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))

    if "price" in data and data["price"] is not None:
        data["price"] = Decimal(str(data["price"]))

    for key, value in data.items():
        setattr(rule, key, value)

    db.commit()
    db.refresh(rule)
    return ResponseModel(message="已更新", data=_pricing_to_dict(rule))


@router.delete("/pricing/{rule_id}", response_model=ResponseModel)
def delete_pricing_rule(
    rule_id: int,
    _: object = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    rule = db.get(PricingRule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="价格规则不存在")
    db.delete(rule)
    db.commit()
    return ResponseModel(message="已删除")


class AdminBalanceAdjustRequest(BaseModel):
    amount: float
    remark: str = "管理员调整余额"


class AdminStudyGoalUpdateRequest(BaseModel):
    study_goal: str | None = None


DEFAULT_NICKNAME = "知行岛学员"


def _needs_profile_setup(user: User) -> bool:
    return not user.avatar_url or user.nickname in (None, "", DEFAULT_NICKNAME)


def _user_admin_item(user: User) -> dict:
    goal = user.study_goal if user.study_goal in STUDY_GOAL_LABELS else None
    return {
        "id": user.id,
        "nickname": user.nickname,
        "phone": user.phone,
        "avatar_url": user.avatar_url,
        "title": user.title,
        "balance": float(user.balance or 0),
        "total_points": user.total_points or 0,
        "invite_code": user.invite_code,
        "study_goal": goal,
        "study_goal_label": STUDY_GOAL_LABELS.get(goal) if goal else None,
        "needs_profile_setup": _needs_profile_setup(user),
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


def _reservation_admin_item(db: Session, r: Reservation) -> dict | None:
    from app.api.routes.reservation import _safe_to_item

    item = _safe_to_item(db, r)
    if not item:
        return None
    base = item.model_dump()
    user = db.get(User, r.user_id)
    base["user_id"] = r.user_id
    base["user_nickname"] = user.nickname if user else None
    base["user_phone"] = user.phone if user else None
    base["pay_type"] = r.pay_type.value if r.pay_type else None
    return base


def _sync_reservation_rows_on_read(db: Session, rows: list[Reservation]) -> None:
    """列表读取时同步过期/自动入座，失败时不阻断列表返回。"""
    now = datetime.now()
    changed = False
    for row in rows:
        try:
            if finalize_expired_reservation(db, row, now):
                changed = True
            elif auto_checkin_reservation(db, row, when=now):
                changed = True
        except Exception:
            continue
    if not changed:
        return
    try:
        db.commit()
        for row in rows:
            db.refresh(row)
    except Exception:
        db.rollback()


@router.post("/reservations/{reservation_id}/cancel", response_model=ResponseModel)
def admin_cancel_reservation(
    reservation_id: int,
    _: object = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    reservation = db.get(Reservation, reservation_id)
    if not reservation:
        raise HTTPException(status_code=404, detail="订单不存在")
    if reservation.status == 3:
        raise HTTPException(status_code=400, detail="订单已取消")
    if reservation.status == 2:
        raise HTTPException(status_code=400, detail="订单已完成，不可取消")
    if reservation.status == 1:
        raise HTTPException(status_code=400, detail="使用中，请先强制离座")

    if reservation.pay_status == 0:
        reservation.status = 3
        db.commit()
        return ResponseModel(message="未支付订单已取消，座位已释放")

    user = db.get(User, reservation.user_id)
    if reservation.pay_status == 1 and user:
        amount = reservation.final_price or Decimal("0")
        if reservation.pay_type == PayType.balance and amount > 0:
            add_wallet_log(
                db, user, "refund", amount,
                f"预约退款-{reservation.order_no}", reservation.order_no,
            )
            reservation.pay_status = 2
        elif reservation.pay_type == PayType.wechat and amount > 0:
            WechatPayService.refund(
                reservation.order_no, amount, amount, "管理员取消预约",
            )
            reservation.pay_status = 2
        elif reservation.pay_type == PayType.period_card:
            if reservation.period_card_id:
                card = db.get(PeriodCard, reservation.period_card_id)
                if card:
                    refund_period_card_consume(
                        card,
                        reservation.bill_type,
                        reservation.start_time,
                        reservation.end_time,
                    )
            reservation.pay_status = 2

    reservation.status = 3
    db.commit()
    return ResponseModel(message="订单已取消")


class AdminChangeSeatRequest(BaseModel):
    seat_id: int


@router.get("/reservations/{reservation_id}/seat-options", response_model=ResponseModel)
def admin_reservation_seat_options(
    reservation_id: int,
    _: object = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    reservation = db.get(Reservation, reservation_id)
    if not reservation:
        raise HTTPException(status_code=404, detail="订单不存在")
    if reservation.pay_status != 1:
        raise HTTPException(status_code=400, detail="仅已付款订单可换座")
    if reservation.status not in (0, 1):
        raise HTTPException(status_code=400, detail="当前订单状态不可换座")
    if reservation.end_time <= datetime.now():
        raise HTTPException(status_code=400, detail="预约已结束，不可换座")

    current = db.get(Seat, reservation.seat_id)
    return ResponseModel(
        data={
            "reservation_id": reservation.id,
            "order_no": reservation.order_no,
            "store_id": reservation.store_id,
            "current_seat_id": reservation.seat_id,
            "current_seat_code": current.seat_code if current else None,
            "start_time": reservation.start_time.isoformat(),
            "end_time": reservation.end_time.isoformat(),
            "seats": seat_options_for_change(db, reservation),
        }
    )


@router.post("/reservations/{reservation_id}/change-seat", response_model=ResponseModel)
def admin_change_reservation_seat(
    reservation_id: int,
    body: AdminChangeSeatRequest,
    _: object = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    reservation = db.get(Reservation, reservation_id)
    if not reservation:
        raise HTTPException(status_code=404, detail="订单不存在")
    try:
        new_seat, old_seat = change_reservation_seat(db, reservation, body.seat_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    db.commit()
    db.refresh(reservation)
    return ResponseModel(
        message=f"已换座：{old_seat.seat_code} → {new_seat.seat_code}",
        data=_reservation_admin_item(db, reservation),
    )


@router.post("/reservations/{reservation_id}/remote-unlock", response_model=ResponseModel)
async def admin_reservation_remote_unlock(
    reservation_id: int,
    _: object = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    reservation = db.get(Reservation, reservation_id)
    if not reservation:
        raise HTTPException(status_code=404, detail="订单不存在")
    try:
        data = await admin_remote_unlock(db, reservation)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    db.commit()
    return ResponseModel(message="远程开门成功", data=data)


@router.post("/reservations/{reservation_id}/force-checkout", response_model=ResponseModel)
def admin_reservation_force_checkout(
    reservation_id: int,
    _: object = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    reservation = db.get(Reservation, reservation_id)
    if not reservation:
        raise HTTPException(status_code=404, detail="订单不存在")
    try:
        admin_force_checkout(db, reservation)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    db.commit()
    db.refresh(reservation)
    return ResponseModel(
        message="已强制离座",
        data=_reservation_admin_item(db, reservation),
    )


@router.get("/users", response_model=ResponseModel)
def list_users_admin(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: str | None = None,
    study_goal: str | None = Query(None, description="kaoyan|kaogong|other|unset"),
    _: object = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    query = select(User)
    if keyword:
        kw = keyword.strip()
        if kw.isdigit():
            query = query.where(
                or_(User.id == int(kw), User.phone.contains(kw), User.invite_code.contains(kw))
            )
        else:
            query = query.where(or_(User.nickname.contains(kw), User.phone.contains(kw)))
    if study_goal == "unset":
        query = query.where(or_(User.study_goal.is_(None), User.study_goal == ""))
    elif study_goal in STUDY_GOAL_LABELS:
        query = query.where(User.study_goal == study_goal)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.scalars(
        query.order_by(User.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return ResponseModel(
        data=PageResult(
            items=[_user_admin_item(u) for u in rows],
            total=total or 0,
            page=page,
            page_size=page_size,
        )
    )


@router.get("/users/study-goal-stats", response_model=ResponseModel)
def user_study_goal_stats(
    _: object = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    total = db.scalar(select(func.count()).select_from(User)) or 0
    breakdown = []
    filled = 0
    for key, label in STUDY_GOAL_LABELS.items():
        count = db.scalar(select(func.count()).where(User.study_goal == key)) or 0
        filled += count
        breakdown.append({"key": key, "label": label, "count": count})
    unset = total - filled
    breakdown.append({"key": "unset", "label": "未填写", "count": unset})
    return ResponseModel(
        data={
            "total": total,
            "filled": filled,
            "unset": unset,
            "breakdown": breakdown,
        }
    )


@router.get("/users/{user_id}", response_model=ResponseModel)
def get_user_admin(
    user_id: int,
    _: object = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    order_count = db.scalar(
        select(func.count()).where(Reservation.user_id == user_id, Reservation.pay_status == 1)
    )
    card_count = db.scalar(
        select(func.count()).where(PeriodCard.user_id == user_id, PeriodCard.status == 1)
    )
    data = _user_admin_item(user)
    data["paid_order_count"] = order_count or 0
    data["active_card_count"] = card_count or 0
    return ResponseModel(data=data)


@router.get("/users/{user_id}/overview", response_model=ResponseModel)
def get_user_overview_admin(
    user_id: int,
    _: object = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    try:
        data = user_overview(db, user_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    user = db.get(User, user_id)
    data["profile"] = _user_admin_item(user)
    data["profile"]["paid_order_count"] = db.scalar(
        select(func.count()).where(Reservation.user_id == user_id, Reservation.pay_status == 1)
    ) or 0
    data["profile"]["active_card_count"] = db.scalar(
        select(func.count()).where(PeriodCard.user_id == user_id, PeriodCard.status == 1)
    ) or 0
    return ResponseModel(data=data)


@router.post("/users/{user_id}/adjust-balance", response_model=ResponseModel)
def adjust_user_balance(
    user_id: int,
    body: AdminBalanceAdjustRequest,
    _: object = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    amount = Decimal(str(body.amount))
    if amount == 0:
        raise HTTPException(status_code=400, detail="调整金额不能为 0")
    if amount < 0 and user.balance + amount < 0:
        raise HTTPException(status_code=400, detail="余额不足，无法扣减")
    log_type = "recharge" if amount > 0 else "consume"
    try:
        add_wallet_log(db, user, log_type, abs(amount), body.remark)
    except ValueError:
        raise HTTPException(status_code=400, detail="余额不足，无法扣减")
    db.commit()
    db.refresh(user)
    return ResponseModel(message="余额已调整", data=_user_admin_item(user))


@router.put("/users/{user_id}/study-goal", response_model=ResponseModel)
def update_user_study_goal(
    user_id: int,
    body: AdminStudyGoalUpdateRequest,
    _: object = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if body.study_goal is not None and body.study_goal != "":
        if body.study_goal not in STUDY_GOAL_LABELS:
            raise HTTPException(status_code=400, detail="备考方向无效")
        user.study_goal = body.study_goal
    else:
        user.study_goal = None
    db.commit()
    db.refresh(user)
    return ResponseModel(message="备考方向已更新", data=_user_admin_item(user))


@router.get("/period-cards", response_model=ResponseModel)
def list_period_cards_admin(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user_id: int | None = None,
    status: int | None = None,
    _: object = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    query = select(PeriodCard)
    if user_id:
        query = query.where(PeriodCard.user_id == user_id)
    if status is not None:
        query = query.where(PeriodCard.status == status)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.scalars(
        query.order_by(PeriodCard.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    today = date.today()
    repaired = False
    items = []
    for card in rows:
        if repair_misissued_card_validity(card):
            repaired = True
        items.append(period_card_admin_dict(db, card, today))
    if repaired:
        db.commit()
    return ResponseModel(
        data=PageResult(items=items, total=total or 0, page=page, page_size=page_size)
    )


class AdminIssuePeriodCardRequest(BaseModel):
    user_id: int
    card_type: str
    reward_value: int = 1
    store_id: int | None = None
    card_name: str | None = None
    remark: str | None = None


class AdminUpdatePeriodCardRequest(BaseModel):
    status: int | None = None
    end_date: date | None = None
    extend_days: int | None = None
    remaining_hours: float | None = None
    total_hours: float | None = None
    remaining_sessions: int | None = None
    remark: str | None = None


@router.post("/period-cards", response_model=ResponseModel)
def issue_period_card_admin(
    body: AdminIssuePeriodCardRequest,
    _: object = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    try:
        card_type = CardType(body.card_type)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="卡类型无效") from e
    try:
        card = issue_admin_period_card(
            db,
            user_id=body.user_id,
            card_type=card_type,
            reward_value=body.reward_value,
            store_id=body.store_id,
            card_name=body.card_name,
            remark=body.remark,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    db.commit()
    db.refresh(card)
    return ResponseModel(message="期限卡已发放", data=period_card_admin_dict(db, card))


@router.patch("/period-cards/{card_id}", response_model=ResponseModel)
def update_period_card_admin(
    card_id: int,
    body: AdminUpdatePeriodCardRequest,
    _: object = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    card = db.get(PeriodCard, card_id)
    if not card:
        raise HTTPException(status_code=404, detail="期限卡不存在")
    try:
        update_admin_period_card(
            db,
            card,
            status=body.status,
            end_date=body.end_date,
            extend_days=body.extend_days,
            remaining_hours=Decimal(str(body.remaining_hours)) if body.remaining_hours is not None else None,
            total_hours=Decimal(str(body.total_hours)) if body.total_hours is not None else None,
            remaining_sessions=body.remaining_sessions,
            remark=body.remark,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    db.commit()
    db.refresh(card)
    return ResponseModel(message="期限卡已更新", data=period_card_admin_dict(db, card))


@router.get("/card-purchase-orders", response_model=ResponseModel)
def list_card_purchase_orders_admin(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user_id: int | None = None,
    store_id: int | None = None,
    pay_status: int | None = None,
    order_no: str | None = None,
    _: object = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    query = select(CardPurchaseOrder)
    if user_id:
        query = query.where(CardPurchaseOrder.user_id == user_id)
    if store_id:
        query = query.where(CardPurchaseOrder.store_id == store_id)
    if pay_status is not None:
        query = query.where(CardPurchaseOrder.pay_status == pay_status)
    if order_no:
        query = query.where(CardPurchaseOrder.order_no.contains(order_no.strip()))
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.scalars(
        query.order_by(CardPurchaseOrder.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    items = []
    for order in rows:
        user = db.get(User, order.user_id)
        store = db.get(Store, order.store_id)
        card = db.get(PeriodCard, order.period_card_id) if order.period_card_id else None
        items.append({
            "id": order.id,
            "order_no": order.order_no,
            "user_id": order.user_id,
            "user_nickname": user.nickname if user else None,
            "user_phone": user.phone if user else None,
            "store_id": order.store_id,
            "store_name": store.name if store else None,
            "bill_type": order.bill_type.value,
            "bill_type_label": BILL_TYPE_LABELS.get(order.bill_type, order.bill_type.value),
            "amount": float(order.amount),
            "pay_type": order.pay_type.value if order.pay_type else None,
            "pay_status": order.pay_status,
            "period_card_id": order.period_card_id,
            "card_name": card.card_name if card else None,
            "created_at": order.created_at.isoformat() if order.created_at else None,
        })
    return ResponseModel(
        data=PageResult(items=items, total=total or 0, page=page, page_size=page_size)
    )


@router.get("/exchange-records", response_model=ResponseModel)
def list_exchange_records_admin(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user_id: int | None = None,
    status: str | None = None,
    _: object = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    query = select(MeituanOrder)
    if user_id:
        query = query.where(MeituanOrder.user_id == user_id)
    if status:
        query = query.where(MeituanOrder.status == status)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.scalars(
        query.order_by(MeituanOrder.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    items = []
    for row in rows:
        user = db.get(User, row.user_id) if row.user_id else None
        items.append({
            "id": row.id,
            "user_id": row.user_id,
            "user_nickname": user.nickname if user else None,
            "coupon_code": row.coupon_code,
            "deal_name": row.deal_name,
            "deal_type": row.deal_type,
            "status": row.status.value,
            "verified_at": row.verified_at.isoformat() if row.verified_at else None,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        })
    return ResponseModel(
        data=PageResult(items=items, total=total or 0, page=page, page_size=page_size)
    )


@router.get("/wallet-logs", response_model=ResponseModel)
def list_wallet_logs_admin(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user_id: int | None = None,
    log_type: str | None = None,
    _: object = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    query = select(WalletLog)
    if user_id:
        query = query.where(WalletLog.user_id == user_id)
    if log_type:
        query = query.where(WalletLog.type == log_type)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.scalars(
        query.order_by(WalletLog.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    items = []
    for log in rows:
        user = db.get(User, log.user_id)
        items.append({
            "id": log.id,
            "user_id": log.user_id,
            "user_nickname": user.nickname if user else None,
            "type": log.type,
            "amount": float(log.amount or 0),
            "balance_after": float(log.balance_after or 0),
            "remark": log.remark,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        })
    return ResponseModel(
        data=PageResult(items=items, total=total or 0, page=page, page_size=page_size)
    )


class KnowledgeUpdateRequest(BaseModel):
    content: str


@router.get("/knowledge", response_model=ResponseModel)
def get_knowledge_admin(_: object = Depends(get_current_admin)):
    content = assistant_service.load_knowledge()
    return ResponseModel(
        data={
            "content": content,
            "path": "backend/app/knowledge/zhixingdao_kb.md",
            "chars": len(content),
        }
    )


@router.put("/knowledge", response_model=ResponseModel)
def update_knowledge_admin(
    body: KnowledgeUpdateRequest,
    _: object = Depends(get_current_admin),
):
    assistant_service.save_knowledge(body.content)
    content = assistant_service.load_knowledge()
    return ResponseModel(
        message="知识库已保存，AI 助手将使用最新内容",
        data={"chars": len(content)},
    )


@router.post("/system/migrate", response_model=ResponseModel)
def admin_run_schema_migrate(
    _: object = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    result = run_schema_migrations(db)
    return ResponseModel(message="数据库结构检查完成", data=result)


@router.get("/system/status", response_model=ResponseModel)
def system_status_admin(_: object = Depends(get_current_admin), db: Session = Depends(get_db)):
    from app.services.yunlaoban import _use_mock

    pay_cert = Path(settings.wx_pay_key_path)
    kb_content = assistant_service.load_knowledge()
    yunlaoban_ok = bool(
        settings.yunlaoban_client_id and settings.yunlaoban_secret and settings.yunlaoban_shop_id
    )
    appid = (settings.wx_appid or "").strip()
    masked_appid = f"{appid[:6]}***" if len(appid) >= 6 else None
    migration = get_last_migration_result()

    unpaid_count = db.scalar(
        select(func.count()).where(
            Reservation.pay_status == 0,
            Reservation.status != 3,
        )
    ) or 0
    pending_deals = db.scalar(
        select(func.count()).where(PendingDealMapping.status == "pending")
    ) or 0
    incomplete_stores: list[dict] = []
    for store in db.scalars(select(Store).where(Store.status == 1)).all():
        summary = store_seat_summary(db, store.id)
        if not summary["is_complete"]:
            incomplete_stores.append(summary)

    checks = [
        {
            "key": "wx_login",
            "name": "微信登录",
            "ok": settings.wx_login_configured or settings.pre_wechat_launch,
            "detail": "已配置 AppID" if settings.wx_login_configured else "审核期可用 dev 登录",
        },
        {
            "key": "wx_pay",
            "name": "微信支付",
            "ok": settings.wx_pay_configured and pay_cert.is_file(),
            "detail": "商户号+证书就绪" if settings.wx_pay_configured and pay_cert.is_file() else "未配置或证书缺失",
        },
        {
            "key": "ttlock",
            "name": "通通锁",
            "ok": bool((settings.ttlock_client_id or "").strip()),
            "detail": "已填凭证" if settings.ttlock_client_id else "未配置",
        },
        {
            "key": "yunlaoban",
            "name": "团购核销",
            "ok": yunlaoban_ok and not _use_mock(),
            "detail": f"provider={settings.coupon_provider}, mock={_use_mock()}",
        },
        {
            "key": "deepseek",
            "name": "AI 助手",
            "ok": settings.assistant_configured,
            "detail": "DeepSeek 已配置" if settings.assistant_configured else "缺少 DEEPSEEK_API_KEY",
        },
        {
            "key": "knowledge",
            "name": "AI 知识库",
            "ok": len(kb_content) > 100,
            "detail": f"{len(kb_content)} 字",
        },
        {
            "key": "database",
            "name": "数据库结构",
            "ok": migration.get("status") in ("ok", "unknown") and not migration.get("errors"),
            "detail": f"回填小时卡 {migration.get('backfill_hours', 0)} 条"
            if migration.get("backfill_hours")
            else "结构已就绪",
        },
    ]

    return ResponseModel(
        data={
            "app_env": settings.app_env,
            "base_url": settings.base_url,
            "pre_wechat_launch": settings.pre_wechat_launch,
            "wx_appid": masked_appid,
            "checks": checks,
            "all_ok": all(c["ok"] for c in checks),
            "migration": migration,
            "ops_todos": {
                "unpaid_orders": unpaid_count,
                "pending_deal_mappings": pending_deals,
                "incomplete_seat_stores": incomplete_stores,
            },
            "health_alert_webhook": bool((settings.health_alert_webhook or "").strip()),
        }
    )


@router.get("/study/overview", response_model=ResponseModel)
def study_overview_admin(_: object = Depends(get_current_admin), db: Session = Depends(get_db)):
    today = date.today()
    week_since = today - timedelta(days=6)

    total_minutes = int(
        db.scalar(select(func.coalesce(func.sum(StudyStat.total_minutes), 0))) or 0
    )
    total_sessions = int(
        db.scalar(select(func.coalesce(func.sum(StudyStat.session_count), 0))) or 0
    )
    learner_count = db.scalar(select(func.count(func.distinct(StudyStat.user_id)))) or 0
    week_minutes = int(
        db.scalar(
            select(func.coalesce(func.sum(StudyStat.total_minutes), 0)).where(
                StudyStat.stat_date >= week_since
            )
        )
        or 0
    )
    week_learners = db.scalar(
        select(func.count(func.distinct(StudyStat.user_id))).where(StudyStat.stat_date >= week_since)
    ) or 0
    today_minutes = int(
        db.scalar(
            select(func.coalesce(func.sum(StudyStat.total_minutes), 0)).where(
                StudyStat.stat_date == today
            )
        )
        or 0
    )

    daily_rows = db.execute(
        select(
            StudyStat.stat_date,
            func.sum(StudyStat.total_minutes).label("minutes"),
            func.sum(StudyStat.session_count).label("sessions"),
        )
        .where(StudyStat.stat_date >= week_since)
        .group_by(StudyStat.stat_date)
        .order_by(StudyStat.stat_date)
    ).all()

    return ResponseModel(
        data={
            "total_minutes": total_minutes,
            "total_hours": total_minutes // 60,
            "total_sessions": total_sessions,
            "learner_count": learner_count,
            "week_minutes": week_minutes,
            "week_learners": week_learners,
            "today_minutes": today_minutes,
            "daily": [
                {
                    "date": str(r.stat_date),
                    "minutes": int(r.minutes or 0),
                    "sessions": int(r.sessions or 0),
                }
                for r in daily_rows
            ],
            "study_goal_breakdown": _study_goal_breakdown(db),
        }
    )


def _study_goal_breakdown(db: Session) -> list[dict]:
    items = []
    for key, label in STUDY_GOAL_LABELS.items():
        count = db.scalar(select(func.count()).where(User.study_goal == key)) or 0
        items.append({"key": key, "label": label, "count": count})
    unset = db.scalar(
        select(func.count()).where(or_(User.study_goal.is_(None), User.study_goal == ""))
    ) or 0
    items.append({"key": "unset", "label": "未填写", "count": unset})
    return items


@router.get("/study/leaderboard", response_model=ResponseModel)
def study_leaderboard_admin(
    days: int = Query(30, ge=1, le=365),
    store_id: int | None = None,
    limit: int = Query(50, ge=1, le=100),
    _: object = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    since = date.today() - timedelta(days=days - 1)
    query = (
        select(
            StudyStat.user_id,
            func.sum(StudyStat.total_minutes).label("total_minutes"),
            func.sum(StudyStat.session_count).label("session_count"),
        )
        .where(StudyStat.stat_date >= since)
        .group_by(StudyStat.user_id)
    )
    if store_id:
        query = query.where(StudyStat.store_id == store_id)
    query = query.order_by(func.sum(StudyStat.total_minutes).desc()).limit(limit)
    rows = db.execute(query).all()

    items = []
    for i, row in enumerate(rows, 1):
        user = db.get(User, row.user_id)
        items.append({
            "rank": i,
            "user_id": row.user_id,
            "nickname": user.nickname if user else "学员",
            "phone": user.phone if user else None,
            "title": user.title if user else "小白",
            "study_goal": user.study_goal if user and user.study_goal in STUDY_GOAL_LABELS else None,
            "study_goal_label": (
                STUDY_GOAL_LABELS.get(user.study_goal)
                if user and user.study_goal in STUDY_GOAL_LABELS
                else None
            ),
            "total_minutes": int(row.total_minutes or 0),
            "session_count": int(row.session_count or 0),
        })
    return ResponseModel(data=items)


class AdminStoreCreateRequest(BaseModel):
    name: str
    address: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    open_time: str | None = None
    close_time: str | None = None
    wifi_name: str | None = None
    wifi_password: str | None = None
    cover_images: list[str] | None = None
    meituan_shop_id: str | None = None


class AdminBannerCreateRequest(BaseModel):
    ribbon: str | None = None
    title_line1: str | None = None
    title_line2: str | None = None
    date_label: str | None = None
    date_range: str | None = None
    cta_text: str | None = None
    layout_type: str = "text"
    image_url: str | None = None
    link_path: str | None = None
    is_active: int = 1
    sort_order: int = 0


class AdminBannerUpdateRequest(BaseModel):
    ribbon: str | None = None
    title_line1: str | None = None
    title_line2: str | None = None
    date_label: str | None = None
    date_range: str | None = None
    cta_text: str | None = None
    layout_type: str | None = None
    image_url: str | None = None
    link_path: str | None = None
    is_active: int | None = None
    sort_order: int | None = None


class AdminCreateRequest(BaseModel):
    username: str
    password: str
    name: str | None = None


def _banner_dict(row: HomeBanner) -> dict:
    return {
        "id": row.id,
        "ribbon": row.ribbon,
        "title_line1": row.title_line1,
        "title_line2": row.title_line2,
        "date_label": row.date_label,
        "date_range": row.date_range,
        "cta_text": row.cta_text,
        "layout_type": row.layout_type or "text",
        "image_url": public_static_url(row.image_url),
        "link_path": row.link_path,
        "is_active": row.is_active,
        "sort_order": row.sort_order,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


@router.post("/stores", response_model=ResponseModel)
def create_store_admin(
    body: AdminStoreCreateRequest,
    _: object = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    try:
        open_time = _parse_time(body.open_time)
        close_time = _parse_time(body.close_time)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    store = Store(
        name=body.name.strip(),
        address=body.address,
        latitude=Decimal(str(body.latitude)) if body.latitude is not None else None,
        longitude=Decimal(str(body.longitude)) if body.longitude is not None else None,
        open_time=open_time,
        close_time=close_time,
        wifi_name=body.wifi_name,
        wifi_password=body.wifi_password,
        cover_images=_cover_images_to_store(body.cover_images or []),
        meituan_shop_id=body.meituan_shop_id,
        status=1,
    )
    db.add(store)
    db.commit()
    db.refresh(store)
    return ResponseModel(message="门店已创建", data=_store_to_admin_item(store))


@router.post("/stores/upload-cover", response_model=ResponseModel)
async def upload_store_cover_admin(
    file: UploadFile = File(...),
    _: object = Depends(get_current_admin),
):
    """上传门店封面图，保存后写入 cover_images 列表。"""
    content_type = (file.content_type or "").lower()
    if content_type not in BANNER_IMAGE_TYPES:
        raise HTTPException(status_code=400, detail="仅支持 jpg / png / webp / gif")

    content = await file.read()
    if len(content) > 2_000_000:
        raise HTTPException(status_code=400, detail="图片不能超过 2MB")

    ext = BANNER_IMAGE_TYPES[content_type]
    STORE_COVER_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4().hex}.{ext}"
    (STORE_COVER_DIR / filename).write_bytes(content)

    return ResponseModel(
        data={
            "url": public_static_url(f"/static/stores/{filename}"),
            "path": f"/static/stores/{filename}",
        }
    )


class AdminCarouselSettingRequest(BaseModel):
    autoplay: bool = True
    interval: int = 5000
    circular: bool = True
    indicator_dots: bool = True
    hero_height: int = 680
    hero_mode: str = "fullscreen"


def _carousel_setting_dict(row: HomeCarouselSetting) -> dict:
    return {
        "autoplay": bool(row.autoplay),
        "interval": row.interval,
        "circular": bool(row.circular),
        "indicator_dots": bool(row.indicator_dots),
        "hero_height": row.hero_height,
        "hero_mode": row.hero_mode or "fullscreen",
    }


def _get_or_create_carousel_setting(db: Session) -> HomeCarouselSetting:
    row = db.get(HomeCarouselSetting, 1)
    if row:
        return row
    row = HomeCarouselSetting(id=1)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.get("/banners/carousel-settings", response_model=ResponseModel)
def get_carousel_settings_admin(_: object = Depends(get_current_admin), db: Session = Depends(get_db)):
    row = _get_or_create_carousel_setting(db)
    return ResponseModel(data=_carousel_setting_dict(row))


@router.put("/banners/carousel-settings", response_model=ResponseModel)
def update_carousel_settings_admin(
    body: AdminCarouselSettingRequest,
    _: object = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    row = _get_or_create_carousel_setting(db)
    row.autoplay = 1 if body.autoplay else 0
    row.interval = max(2000, min(body.interval, 20000))
    row.circular = 1 if body.circular else 0
    row.indicator_dots = 1 if body.indicator_dots else 0
    row.hero_height = max(360, min(body.hero_height, 880))
    row.hero_mode = body.hero_mode if body.hero_mode in ("fullscreen", "card") else "fullscreen"
    db.commit()
    db.refresh(row)
    return ResponseModel(message="轮播设置已保存", data=_carousel_setting_dict(row))


@router.get("/banners", response_model=ResponseModel)
def list_banners_admin(_: object = Depends(get_current_admin), db: Session = Depends(get_db)):
    rows = db.scalars(select(HomeBanner).order_by(HomeBanner.sort_order, HomeBanner.id.desc())).all()
    return ResponseModel(data=[_banner_dict(r) for r in rows])


@router.post("/banners/upload-image", response_model=ResponseModel)
async def upload_banner_image_admin(
    file: UploadFile = File(...),
    _: object = Depends(get_current_admin),
):
    content_type = (file.content_type or "").lower()
    if content_type not in BANNER_IMAGE_TYPES:
        raise HTTPException(status_code=400, detail="仅支持 jpg / png / webp / gif")

    content = await file.read()
    if len(content) > 2_000_000:
        raise HTTPException(status_code=400, detail="图片不能超过 2MB")

    ext = BANNER_IMAGE_TYPES[content_type]
    BANNER_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4().hex}.{ext}"
    (BANNER_DIR / filename).write_bytes(content)

    base = settings.base_url.rstrip("/")
    return ResponseModel(data={"url": public_static_url(f"/static/banners/{filename}")})


@router.post("/banners", response_model=ResponseModel)
def create_banner_admin(
    body: AdminBannerCreateRequest,
    _: object = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    row = HomeBanner(**body.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return ResponseModel(message="已创建", data=_banner_dict(row))


@router.put("/banners/{banner_id}", response_model=ResponseModel)
def update_banner_admin(
    banner_id: int,
    body: AdminBannerUpdateRequest,
    _: object = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    row = db.get(HomeBanner, banner_id)
    if not row:
        raise HTTPException(status_code=404, detail="活动不存在")
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(row, key, value)
    db.commit()
    db.refresh(row)
    return ResponseModel(message="已更新", data=_banner_dict(row))


@router.get("/point-logs", response_model=ResponseModel)
def list_point_logs_admin(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user_id: int | None = None,
    log_type: str | None = None,
    _: object = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    query = select(PointLog)
    if user_id:
        query = query.where(PointLog.user_id == user_id)
    if log_type:
        query = query.where(PointLog.type == log_type)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.scalars(
        query.order_by(PointLog.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    type_labels = {
        "study": "自习",
        "invite": "邀请奖励",
        "invite_reward": "邀请好友",
        "exchange": "兑换",
    }
    items = []
    for log in rows:
        user = db.get(User, log.user_id)
        items.append({
            "id": log.id,
            "user_id": log.user_id,
            "user_nickname": user.nickname if user else None,
            "type": log.type,
            "type_label": type_labels.get(log.type, log.type),
            "points": log.points,
            "remark": log.remark,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        })
    return ResponseModel(
        data=PageResult(items=items, total=total or 0, page=page, page_size=page_size)
    )


@router.get("/invites", response_model=ResponseModel)
def list_invites_admin(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _: object = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    query = select(User).where(User.invited_by.isnot(None))
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.scalars(
        query.order_by(User.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    items = []
    for user in rows:
        inviter = db.get(User, user.invited_by) if user.invited_by else None
        items.append({
            "user_id": user.id,
            "nickname": user.nickname,
            "phone": user.phone,
            "invited_at": user.created_at.isoformat() if user.created_at else None,
            "inviter_id": inviter.id if inviter else None,
            "inviter_nickname": inviter.nickname if inviter else None,
            "inviter_code": inviter.invite_code if inviter else None,
        })

    total_invites = db.scalar(select(func.count()).where(User.invited_by.isnot(None))) or 0
    inviter_count = db.scalar(
        select(func.count(func.distinct(User.invited_by))).where(User.invited_by.isnot(None))
    ) or 0

    return ResponseModel(
        data={
            "stats": {
                "total_invites": total_invites,
                "inviter_count": inviter_count,
            },
            "items": items,
            "total": total or 0,
            "page": page,
            "page_size": page_size,
        }
    )


@router.get("/admins", response_model=ResponseModel)
def list_admins(_: object = Depends(get_current_admin), db: Session = Depends(get_db)):
    rows = db.scalars(select(AdminUser).order_by(AdminUser.id)).all()
    return ResponseModel(
        data=[
            {
                "id": a.id,
                "username": a.username,
                "name": a.name,
                "status": a.status,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in rows
        ]
    )


@router.post("/admins", response_model=ResponseModel)
def create_admin_user(
    body: AdminCreateRequest,
    _: object = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    if len(body.password) < 6:
        raise HTTPException(status_code=400, detail="密码至少 6 位")
    exists = db.scalar(select(AdminUser).where(AdminUser.username == body.username))
    if exists:
        raise HTTPException(status_code=400, detail="用户名已存在")
    admin = AdminUser(
        username=body.username.strip(),
        password_hash=hash_password(body.password),
        name=body.name,
        status=1,
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    return ResponseModel(
        message="管理员已创建",
        data={"id": admin.id, "username": admin.username, "name": admin.name},
    )
