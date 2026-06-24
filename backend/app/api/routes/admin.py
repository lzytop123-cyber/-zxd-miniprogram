from datetime import date, datetime, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin, get_current_user
from app.core.config import settings
from app.core.security import create_access_token, hash_password, verify_password
from app.db.session import get_db
from app.models import AdminUser, Coupon, MeituanDealMapping, PendingDealMapping, Reservation, RewardType, Seat, Store, User, Zone
from app.schemas.common import PageParams, PageResult, ResponseModel
from app.schemas.reservation import ReservationItem
from app.services.deal_mapping_service import mark_pending_resolved_by_deal_id, resolve_pending_deal

router = APIRouter(prefix="/admin", tags=["后台管理"])


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


@router.get("/reservations", response_model=ResponseModel[PageResult[ReservationItem]])
def admin_reservations(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    store_id: int | None = None,
    pay_status: int | None = None,
    _: object = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    query = select(Reservation)
    if store_id:
        query = query.where(Reservation.store_id == store_id)
    if pay_status is not None:
        query = query.where(Reservation.pay_status == pay_status)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.scalars(
        query.order_by(Reservation.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()

    items = []
    for r in rows:
        from app.api.routes.reservation import _to_item

        items.append(_to_item(db, r))

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


@router.get("/deal-mappings", response_model=ResponseModel)
def list_deal_mappings(_: object = Depends(get_current_admin), db: Session = Depends(get_db)):
    rows = db.scalars(select(MeituanDealMapping).order_by(MeituanDealMapping.id.desc())).all()
    return ResponseModel(
        data=[
            {
                "id": r.id,
                "store_id": r.store_id,
                "deal_id": r.deal_id,
                "deal_name": r.deal_name,
                "reward_type": r.reward_type.value,
                "reward_value": r.reward_value,
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
        is_active=body.is_active,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    mark_pending_resolved_by_deal_id(db, body.deal_id)
    return ResponseModel(message="已添加", data={"id": row.id})


@router.get("/deal-mappings/pending", response_model=ResponseModel)
def list_pending_deal_mappings(_: object = Depends(get_current_admin), db: Session = Depends(get_db)):
    rows = db.scalars(
        select(PendingDealMapping)
        .where(PendingDealMapping.status == "pending")
        .order_by(PendingDealMapping.updated_at.desc())
    ).all()
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
    seats = db.scalars(
        select(Seat)
        .where(Seat.store_id == store_id, Seat.is_buffer == 0)
        .order_by(Seat.seat_code)
    ).all()
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
