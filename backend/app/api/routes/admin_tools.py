"""后台 P2/P3 扩展 API。"""

from __future__ import annotations

from datetime import date, datetime, time

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin
from app.db.session import get_db
from app.models import (
    AdminOperationLog,
    AdminUser,
    PendingDealMapping,
    PricingRule,
    Reservation,
    Seat,
    Store,
    StoreCalendarDay,
    SystemAnnouncement,
    User,
    Zone,
)
from app.schemas.common import PageResult, ResponseModel
from app.services.admin_audit import log_admin_action
from app.services.csv_export import export_reservations_csv, export_study_stats_csv, export_wallet_logs_csv
from app.services.deal_template_service import import_deal_templates, list_deal_templates
from app.services.points import adjust_points
from app.services.seat_setup import store_seat_summary

router = APIRouter(prefix="/admin", tags=["后台扩展"])


def _parse_time(value: str | None) -> time | None:
    if not value or not str(value).strip():
        return None
    parts = str(value).strip().split(":")
    h, m = int(parts[0]), int(parts[1]) if len(parts) > 1 else 0
    return time(h, m)


def _time_to_str(value: time | None) -> str | None:
    return value.strftime("%H:%M") if value else None


class DealImportRequest(BaseModel):
    store_id: int = 1
    platform: int = Field(default=1, ge=1, le=2)
    overwrite: bool = False


class SeatCreateRequest(BaseModel):
    store_id: int
    zone_id: int
    seat_code: str
    seat_type: str = "standard"
    has_outlet: int = 1
    has_curtain: int = 0
    pos_x: int | None = None
    pos_y: int | None = None
    status: int = 1


class SeatUpdateRequest(BaseModel):
    zone_id: int | None = None
    seat_code: str | None = None
    seat_type: str | None = None
    has_outlet: int | None = None
    has_curtain: int | None = None
    pos_x: int | None = None
    pos_y: int | None = None
    status: int | None = None


class PricingCopyRequest(BaseModel):
    overwrite: bool = False


class RefundMarkRequest(BaseModel):
    remark: str = Field(min_length=1, max_length=200)


class PointsAdjustRequest(BaseModel):
    delta: int
    remark: str = "管理员调整积分"


class AnnouncementCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    content: str = Field(min_length=1)
    link_path: str | None = None
    show_on_home: int = 1
    popup_once: int = 1
    priority: int = 0
    is_active: int = 1
    start_at: datetime | None = None
    end_at: datetime | None = None


class AnnouncementUpdateRequest(BaseModel):
    title: str | None = None
    content: str | None = None
    link_path: str | None = None
    show_on_home: int | None = None
    popup_once: int | None = None
    priority: int | None = None
    is_active: int | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None


class CalendarDayRequest(BaseModel):
    day: date
    is_closed: int = 0
    open_time: str | None = None
    close_time: str | None = None
    remark: str | None = None


def _announcement_dict(row: SystemAnnouncement) -> dict:
    return {
        "id": row.id,
        "title": row.title,
        "content": row.content,
        "link_path": row.link_path,
        "show_on_home": row.show_on_home,
        "popup_once": row.popup_once,
        "priority": row.priority,
        "is_active": row.is_active,
        "start_at": row.start_at.isoformat() if row.start_at else None,
        "end_at": row.end_at.isoformat() if row.end_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def _calendar_dict(row: StoreCalendarDay) -> dict:
    return {
        "id": row.id,
        "store_id": row.store_id,
        "day": row.day.isoformat(),
        "is_closed": row.is_closed,
        "open_time": _time_to_str(row.open_time),
        "close_time": _time_to_str(row.close_time),
        "remark": row.remark,
    }


@router.get("/stats/todos", response_model=ResponseModel)
def admin_stats_todos(
    _: object = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    unpaid_count = db.scalar(
        select(func.count()).where(
            Reservation.pay_status == 0,
            Reservation.status != 3,
        )
    ) or 0
    pending_deals = db.scalar(
        select(func.count()).where(PendingDealMapping.status == "pending")
    ) or 0
    from app.models import BleBatteryAlert

    low_battery = db.scalar(
        select(func.count()).where(BleBatteryAlert.is_read == 0)
    ) or 0
    incomplete_stores: list[dict] = []
    for store in db.scalars(select(Store).where(Store.status == 1)).all():
        summary = store_seat_summary(db, store.id)
        if not summary["is_complete"]:
            incomplete_stores.append(summary)
    active_announcements = db.scalar(
        select(func.count()).where(SystemAnnouncement.is_active == 1)
    ) or 0
    return ResponseModel(
        data={
            "unpaid_orders": unpaid_count,
            "pending_deal_mappings": pending_deals,
            "incomplete_seat_stores": incomplete_stores,
            "unread_battery_alerts": low_battery,
            "active_announcements": active_announcements,
        }
    )


@router.get("/deal-mappings/templates", response_model=ResponseModel)
def get_deal_templates(_: object = Depends(get_current_admin)):
    return ResponseModel(data=list_deal_templates())


@router.post("/deal-mappings/import-templates", response_model=ResponseModel)
def post_import_deal_templates(
    body: DealImportRequest,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    try:
        result = import_deal_templates(
            db, body.store_id, platform=body.platform, overwrite=body.overwrite
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    log_admin_action(
        db,
        admin,
        "import_deal_templates",
        target_type="store",
        target_id=body.store_id,
        detail=f"platform={body.platform}, added={result['added']}",
    )
    db.commit()
    return ResponseModel(message="模板导入完成", data=result)


@router.post("/seats", response_model=ResponseModel)
def create_seat_admin(
    body: SeatCreateRequest,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    store = db.get(Store, body.store_id)
    if not store:
        raise HTTPException(status_code=404, detail="门店不存在")
    zone = db.get(Zone, body.zone_id)
    if not zone or zone.store_id != body.store_id:
        raise HTTPException(status_code=400, detail="区域不存在或不属于该门店")
    exists = db.scalar(
        select(Seat).where(Seat.store_id == body.store_id, Seat.seat_code == body.seat_code.strip())
    )
    if exists:
        raise HTTPException(status_code=400, detail="座位编号已存在")
    seat = Seat(
        store_id=body.store_id,
        zone_id=body.zone_id,
        seat_code=body.seat_code.strip(),
        seat_type=body.seat_type,
        has_outlet=body.has_outlet,
        has_curtain=body.has_curtain,
        pos_x=body.pos_x,
        pos_y=body.pos_y,
        status=body.status,
    )
    db.add(seat)
    log_admin_action(db, admin, "create_seat", target_type="seat", target_id=body.seat_code)
    db.commit()
    db.refresh(seat)
    return ResponseModel(message="座位已创建", data={"id": seat.id})


@router.patch("/seats/{seat_id}", response_model=ResponseModel)
def update_seat_admin(
    seat_id: int,
    body: SeatUpdateRequest,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    seat = db.get(Seat, seat_id)
    if not seat:
        raise HTTPException(status_code=404, detail="座位不存在")
    data = body.model_dump(exclude_unset=True)
    if "zone_id" in data:
        zone = db.get(Zone, data["zone_id"])
        if not zone or zone.store_id != seat.store_id:
            raise HTTPException(status_code=400, detail="区域无效")
    if "seat_code" in data and data["seat_code"]:
        data["seat_code"] = data["seat_code"].strip()
        dup = db.scalar(
            select(Seat).where(
                Seat.store_id == seat.store_id,
                Seat.seat_code == data["seat_code"],
                Seat.id != seat.id,
            )
        )
        if dup:
            raise HTTPException(status_code=400, detail="座位编号已存在")
    for key, value in data.items():
        setattr(seat, key, value)
    log_admin_action(db, admin, "update_seat", target_type="seat", target_id=seat_id)
    db.commit()
    return ResponseModel(message="座位已更新")


@router.delete("/seats/{seat_id}", response_model=ResponseModel)
def delete_seat_admin(
    seat_id: int,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    seat = db.get(Seat, seat_id)
    if not seat:
        raise HTTPException(status_code=404, detail="座位不存在")
    used = db.scalar(select(func.count()).where(Reservation.seat_id == seat_id)) or 0
    if used:
        raise HTTPException(status_code=400, detail="该座位有关联订单，请改为停用而非删除")
    db.delete(seat)
    log_admin_action(db, admin, "delete_seat", target_type="seat", target_id=seat_id)
    db.commit()
    return ResponseModel(message="座位已删除")


@router.get("/stores/{store_id}/seats/layout", response_model=ResponseModel)
def store_seats_layout(
    store_id: int,
    _: object = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    store = db.get(Store, store_id)
    if not store:
        raise HTTPException(status_code=404, detail="门店不存在")
    zones = {
        z.id: {"id": z.id, "name": z.name, "type": z.type}
        for z in db.scalars(select(Zone).where(Zone.store_id == store_id)).all()
    }
    seats = db.scalars(
        select(Seat)
        .where(Seat.store_id == store_id, Seat.is_buffer == 0)
        .order_by(Seat.seat_code)
    ).all()
    return ResponseModel(
        data={
            "store_id": store_id,
            "floor_plan": store.floor_plan,
            "zones": list(zones.values()),
            "seats": [
                {
                    "id": s.id,
                    "seat_code": s.seat_code,
                    "zone_id": s.zone_id,
                    "zone_name": zones.get(s.zone_id, {}).get("name", "-"),
                    "seat_type": s.seat_type,
                    "pos_x": s.pos_x,
                    "pos_y": s.pos_y,
                    "status": s.status,
                    "has_outlet": s.has_outlet,
                    "has_curtain": s.has_curtain,
                }
                for s in seats
            ],
        }
    )


@router.post("/stores/{source_id}/pricing/copy-to/{target_id}", response_model=ResponseModel)
def copy_pricing_to_store(
    source_id: int,
    target_id: int,
    body: PricingCopyRequest,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    if source_id == target_id:
        raise HTTPException(status_code=400, detail="源门店与目标门店不能相同")
    source = db.get(Store, source_id)
    target = db.get(Store, target_id)
    if not source or not target:
        raise HTTPException(status_code=404, detail="门店不存在")
    source_rules = db.scalars(select(PricingRule).where(PricingRule.store_id == source_id)).all()
    added = 0
    updated = 0
    for rule in source_rules:
        existing = db.scalar(
            select(PricingRule).where(
                PricingRule.store_id == target_id,
                PricingRule.bill_type == rule.bill_type,
                PricingRule.seat_type == rule.seat_type,
            )
        )
        if existing:
            if body.overwrite:
                existing.price = rule.price
                existing.min_hours = rule.min_hours
                existing.max_hours = rule.max_hours
                existing.valid_days = rule.valid_days
                existing.night_start = rule.night_start
                existing.night_end = rule.night_end
                existing.remark = rule.remark
                existing.sort_order = rule.sort_order
                existing.is_active = rule.is_active
                updated += 1
            continue
        db.add(
            PricingRule(
                store_id=target_id,
                bill_type=rule.bill_type,
                seat_type=rule.seat_type,
                price=rule.price,
                min_hours=rule.min_hours,
                max_hours=rule.max_hours,
                valid_days=rule.valid_days,
                night_start=rule.night_start,
                night_end=rule.night_end,
                remark=rule.remark,
                sort_order=rule.sort_order,
                is_active=rule.is_active,
            )
        )
        added += 1
    log_admin_action(
        db,
        admin,
        "copy_pricing",
        target_type="store",
        target_id=target_id,
        detail=f"from={source_id}, added={added}, updated={updated}",
    )
    db.commit()
    return ResponseModel(message="定价已复制", data={"added": added, "updated": updated})


@router.get("/export/reservations")
def export_reservations(
    store_id: int | None = None,
    _: object = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    filename, content = export_reservations_csv(db, store_id=store_id)
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/export/wallet-logs")
def export_wallet_logs(
    user_id: int | None = None,
    _: object = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    filename, content = export_wallet_logs_csv(db, user_id=user_id)
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/export/study-stats")
def export_study_stats(
    _: object = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    filename, content = export_study_stats_csv(db)
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/reservations/{reservation_id}/mark-refund", response_model=ResponseModel)
def mark_reservation_refund(
    reservation_id: int,
    body: RefundMarkRequest,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    reservation = db.get(Reservation, reservation_id)
    if not reservation:
        raise HTTPException(status_code=404, detail="订单不存在")
    if reservation.pay_status != 1:
        raise HTTPException(status_code=400, detail="仅已付款订单可登记退款")
    reservation.pay_status = 2
    reservation.refund_remark = body.remark.strip()
    reservation.refunded_at = datetime.now()
    if reservation.status in (0, 1):
        reservation.status = 3
    log_admin_action(
        db,
        admin,
        "mark_refund",
        target_type="reservation",
        target_id=reservation.order_no,
        detail=body.remark,
    )
    db.commit()
    return ResponseModel(message="已登记退款")


@router.post("/users/{user_id}/adjust-points", response_model=ResponseModel)
def admin_adjust_points(
    user_id: int,
    body: PointsAdjustRequest,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    try:
        adjust_points(db, user, body.delta, body.remark)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    log_admin_action(
        db,
        admin,
        "adjust_points",
        target_type="user",
        target_id=user_id,
        detail=f"delta={body.delta}, remark={body.remark}",
    )
    db.commit()
    db.refresh(user)
    return ResponseModel(
        message="积分已调整",
        data={"id": user.id, "total_points": user.total_points},
    )


@router.get("/operation-logs", response_model=ResponseModel)
def list_operation_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    action: str | None = None,
    _: object = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    query = select(AdminOperationLog)
    if action:
        query = query.where(AdminOperationLog.action.contains(action.strip()))
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.scalars(
        query.order_by(AdminOperationLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    items = [
        {
            "id": r.id,
            "admin_id": r.admin_id,
            "admin_username": r.admin_username,
            "action": r.action,
            "target_type": r.target_type,
            "target_id": r.target_id,
            "detail": r.detail,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]
    return ResponseModel(data=PageResult(items=items, total=total or 0, page=page, page_size=page_size))


@router.get("/announcements", response_model=ResponseModel)
def list_announcements_admin(_: object = Depends(get_current_admin), db: Session = Depends(get_db)):
    rows = db.scalars(
        select(SystemAnnouncement).order_by(SystemAnnouncement.priority.desc(), SystemAnnouncement.id.desc())
    ).all()
    return ResponseModel(data=[_announcement_dict(r) for r in rows])


@router.post("/announcements", response_model=ResponseModel)
def create_announcement(
    body: AnnouncementCreateRequest,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    row = SystemAnnouncement(**body.model_dump())
    db.add(row)
    log_admin_action(db, admin, "create_announcement", target_type="announcement", detail=body.title)
    db.commit()
    db.refresh(row)
    return ResponseModel(message="公告已创建", data=_announcement_dict(row))


@router.patch("/announcements/{announcement_id}", response_model=ResponseModel)
def update_announcement(
    announcement_id: int,
    body: AnnouncementUpdateRequest,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    row = db.get(SystemAnnouncement, announcement_id)
    if not row:
        raise HTTPException(status_code=404, detail="公告不存在")
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(row, key, value)
    log_admin_action(db, admin, "update_announcement", target_type="announcement", target_id=announcement_id)
    db.commit()
    return ResponseModel(message="公告已更新", data=_announcement_dict(row))


@router.delete("/announcements/{announcement_id}", response_model=ResponseModel)
def delete_announcement(
    announcement_id: int,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    row = db.get(SystemAnnouncement, announcement_id)
    if not row:
        raise HTTPException(status_code=404, detail="公告不存在")
    db.delete(row)
    log_admin_action(db, admin, "delete_announcement", target_type="announcement", target_id=announcement_id)
    db.commit()
    return ResponseModel(message="公告已删除")


@router.get("/stores/{store_id}/calendar", response_model=ResponseModel)
def list_store_calendar(
    store_id: int,
    from_day: date | None = None,
    to_day: date | None = None,
    _: object = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    store = db.get(Store, store_id)
    if not store:
        raise HTTPException(status_code=404, detail="门店不存在")
    query = select(StoreCalendarDay).where(StoreCalendarDay.store_id == store_id)
    if from_day:
        query = query.where(StoreCalendarDay.day >= from_day)
    if to_day:
        query = query.where(StoreCalendarDay.day <= to_day)
    rows = db.scalars(query.order_by(StoreCalendarDay.day)).all()
    return ResponseModel(data=[_calendar_dict(r) for r in rows])


@router.put("/stores/{store_id}/calendar/{day_str}", response_model=ResponseModel)
def upsert_store_calendar_day(
    store_id: int,
    day_str: str,
    body: CalendarDayRequest,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    store = db.get(Store, store_id)
    if not store:
        raise HTTPException(status_code=404, detail="门店不存在")
    try:
        day = date.fromisoformat(day_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="日期格式应为 YYYY-MM-DD")
    row = db.scalar(
        select(StoreCalendarDay).where(StoreCalendarDay.store_id == store_id, StoreCalendarDay.day == day)
    )
    if not row:
        row = StoreCalendarDay(store_id=store_id, day=day)
        db.add(row)
    row.is_closed = body.is_closed
    row.open_time = _parse_time(body.open_time)
    row.close_time = _parse_time(body.close_time)
    row.remark = body.remark
    log_admin_action(db, admin, "upsert_calendar", target_type="store", target_id=store_id, detail=day_str)
    db.commit()
    db.refresh(row)
    return ResponseModel(message="日历已保存", data=_calendar_dict(row))


@router.delete("/stores/{store_id}/calendar/{day_str}", response_model=ResponseModel)
def delete_store_calendar_day(
    store_id: int,
    day_str: str,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    try:
        day = date.fromisoformat(day_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="日期格式应为 YYYY-MM-DD")
    row = db.scalar(
        select(StoreCalendarDay).where(StoreCalendarDay.store_id == store_id, StoreCalendarDay.day == day)
    )
    if not row:
        raise HTTPException(status_code=404, detail="日历记录不存在")
    db.delete(row)
    log_admin_action(db, admin, "delete_calendar", target_type="store", target_id=store_id, detail=day_str)
    db.commit()
    return ResponseModel(message="日历记录已删除")
