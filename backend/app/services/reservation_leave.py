"""月卡请假/停卡服务（每张月卡最多 3 次，方案 A：原订单顺延并排座）。"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Iterable

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    AdminUser,
    BillType,
    Reservation,
    ReservationLeave,
    Seat,
    Store,
)
from app.services.admin_audit import log_admin_action

MONTHLY_LEAVE_LIMIT = 3
MONTHLY_LEAVE_BILL_TYPES = {BillType.monthly, BillType.night_monthly}


def is_monthly_leave_eligible(reservation: Reservation) -> bool:
    return reservation.bill_type in MONTHLY_LEAVE_BILL_TYPES


def get_active_leaves_for_reservation(
    db: Session,
    reservation_id: int,
) -> list[ReservationLeave]:
    return list(
        db.scalars(
            select(ReservationLeave)
            .where(
                ReservationLeave.reservation_id == reservation_id,
                ReservationLeave.status == "active",
            )
            .order_by(ReservationLeave.start_date.asc(), ReservationLeave.id.asc())
        ).all()
    )


def get_active_leaves_map(
    db: Session,
    reservation_ids: Iterable[int],
) -> dict[int, list[tuple[date, date]]]:
    ids = [int(i) for i in set(reservation_ids) if i]
    if not ids:
        return {}
    rows = db.scalars(
        select(ReservationLeave).where(
            ReservationLeave.reservation_id.in_(ids),
            ReservationLeave.status == "active",
        )
    ).all()
    out: dict[int, list[tuple[date, date]]] = {}
    for row in rows:
        out.setdefault(row.reservation_id, []).append((row.start_date, row.end_date))
    return out


def count_used_leaves(db: Session, reservation: Reservation) -> int:
    """统计该月卡已使用的有效请假次数（同 period_card_id 共享 3 次额度）。"""
    if reservation.period_card_id:
        rows = db.scalars(
            select(ReservationLeave.id).where(
                ReservationLeave.period_card_id == reservation.period_card_id,
                ReservationLeave.status == "active",
            )
        ).all()
        return len(rows)
    rows = db.scalars(
        select(ReservationLeave.id).where(
            ReservationLeave.reservation_id == reservation.id,
            ReservationLeave.status == "active",
        )
    ).all()
    return len(rows)


def get_active_leave_on_date(
    db: Session,
    reservation_id: int,
    day: date | None = None,
) -> ReservationLeave | None:
    target = day or datetime.now().date()
    return db.scalar(
        select(ReservationLeave).where(
            ReservationLeave.reservation_id == reservation_id,
            ReservationLeave.status == "active",
            ReservationLeave.start_date <= target,
            ReservationLeave.end_date >= target,
        )
    )


def is_reservation_on_leave(
    db: Session,
    reservation_id: int,
    at: datetime | None = None,
) -> ReservationLeave | None:
    target_date = (at or datetime.now()).date()
    return get_active_leave_on_date(db, reservation_id, target_date)


def _date_ranges_overlap(a_start: date, a_end: date, b_start: date, b_end: date) -> bool:
    return a_start <= b_end and b_start <= a_end


def _serialize_leave(db: Session, row: ReservationLeave) -> dict:
    orig_seat = db.get(Seat, row.original_seat_id)
    tgt_seat = db.get(Seat, row.target_seat_id)
    today = datetime.now().date()
    return {
        "id": row.id,
        "reservation_id": row.reservation_id,
        "start_date": row.start_date.isoformat(),
        "end_date": row.end_date.isoformat(),
        "days": row.days,
        "status": row.status,
        "prev_end_time": row.prev_end_time.strftime("%Y-%m-%d %H:%M"),
        "new_end_time": row.new_end_time.strftime("%Y-%m-%d %H:%M"),
        "original_seat_id": row.original_seat_id,
        "original_seat_code": orig_seat.seat_code if orig_seat else None,
        "target_seat_id": row.target_seat_id,
        "target_seat_code": tgt_seat.seat_code if tgt_seat else None,
        "reason": row.reason or "",
        "created_at": row.created_at.strftime("%Y-%m-%d %H:%M") if row.created_at else None,
        "cancelled_at": row.cancelled_at.strftime("%Y-%m-%d %H:%M") if row.cancelled_at else None,
        "can_cancel": row.status == "active" and today <= row.end_date,
        "is_ongoing": row.status == "active" and row.start_date <= today <= row.end_date,
    }


def _validate_leave_request(
    db: Session,
    reservation: Reservation,
    start_date: date,
    end_date: date,
    now: datetime | None = None,
) -> tuple[int, datetime, datetime]:
    now = now or datetime.now()
    today = now.date()

    if not is_monthly_leave_eligible(reservation):
        raise HTTPException(status_code=400, detail="仅月卡订单支持请假（每周/天/小时/季卡不适用）")
    if reservation.pay_status != 1 or reservation.status not in (0, 1):
        raise HTTPException(status_code=400, detail="仅已付款且进行中的月卡订单可办理请假")

    used = count_used_leaves(db, reservation)
    if used >= MONTHLY_LEAVE_LIMIT:
        raise HTTPException(status_code=400, detail=f"该月卡已用完 {MONTHLY_LEAVE_LIMIT} 次请假额度")

    if start_date > end_date:
        raise HTTPException(status_code=400, detail="请假结束日期不能早于开始日期")
    if end_date < today:
        raise HTTPException(status_code=400, detail="不能对已经过去的日期办理请假")

    res_start_date = reservation.start_time.date()
    res_end_date = reservation.end_time.date()
    if start_date < res_start_date or end_date > res_end_date:
        raise HTTPException(
            status_code=400,
            detail=f"请假日期须在当前预约期内（{res_start_date} 至 {res_end_date}）",
        )

    existing = get_active_leaves_for_reservation(db, reservation.id)
    for lv in existing:
        if _date_ranges_overlap(start_date, end_date, lv.start_date, lv.end_date):
            raise HTTPException(
                status_code=400,
                detail=f"请假日期与已有请假（{lv.start_date} 至 {lv.end_date}）重叠",
            )

    days = (end_date - start_date).days + 1
    prev_end_time = reservation.end_time
    new_end_time = prev_end_time + timedelta(days=days)
    return days, prev_end_time, new_end_time


def preview_monthly_leave(
    db: Session,
    reservation: Reservation,
    start_date: date,
    end_date: date,
) -> dict:
    """预览月卡请假顺延结果及顺延时段原座/替代座可用情况。"""
    from app.services.business import find_seat_conflict, find_busy_seat_ids
    from app.services.store_seat_maps import list_bookable_seats

    days, prev_end_time, new_end_time = _validate_leave_request(db, reservation, start_date, end_date)
    conflict = find_seat_conflict(
        db,
        reservation.seat_id,
        prev_end_time,
        new_end_time,
        exclude_reservation_id=reservation.id,
    )
    orig_seat = db.get(Seat, reservation.seat_id)
    store = db.get(Store, reservation.store_id)
    alt_seats: list[dict] = []

    if conflict and store:
        bookable = list_bookable_seats(db, store)
        candidate_ids = [s.id for s in bookable if s.id != reservation.seat_id]
        # 替代座位需要从现在（或预约开始）到顺延结束都可用
        check_start = max(datetime.now(), reservation.start_time)
        busy_ids = find_busy_seat_ids(db, candidate_ids, check_start, new_end_time)
        for s in bookable:
            if s.id == reservation.seat_id or s.id in busy_ids:
                continue
            alt_seats.append({
                "id": s.id,
                "seat_code": s.seat_code,
                "zone_name": s.zone.name if s.zone else "",
            })

    return {
        "days": days,
        "used_count": count_used_leaves(db, reservation),
        "limit": MONTHLY_LEAVE_LIMIT,
        "prev_end_time": prev_end_time.strftime("%Y-%m-%d %H:%M"),
        "new_end_time": new_end_time.strftime("%Y-%m-%d %H:%M"),
        "original_seat_id": reservation.seat_id,
        "original_seat_code": orig_seat.seat_code if orig_seat else "",
        "original_seat_available": conflict is None,
        "conflict_order_no": conflict.order_no if conflict else None,
        "alternative_seats": alt_seats,
    }


def list_reservation_leaves_payload(db: Session, reservation: Reservation) -> dict:
    rows = db.scalars(
        select(ReservationLeave)
        .where(ReservationLeave.reservation_id == reservation.id)
        .order_by(ReservationLeave.created_at.desc(), ReservationLeave.id.desc())
    ).all()
    return {
        "reservation_id": reservation.id,
        "order_no": reservation.order_no,
        "eligible": is_monthly_leave_eligible(reservation) and reservation.pay_status == 1 and reservation.status in (0, 1),
        "used_count": count_used_leaves(db, reservation),
        "limit": MONTHLY_LEAVE_LIMIT,
        "start_time": reservation.start_time.strftime("%Y-%m-%d %H:%M"),
        "end_time": reservation.end_time.strftime("%Y-%m-%d %H:%M"),
        "leaves": [_serialize_leave(db, r) for r in rows],
    }


def create_monthly_leave(
    db: Session,
    reservation: Reservation,
    start_date: date,
    end_date: date,
    admin: AdminUser,
    target_seat_id: int | None = None,
    reason: str | None = None,
) -> dict:
    """办理月卡请假：记录停卡区间 + 顺延原订单结束时间 + 冲突时换座。"""
    from app.services.business import find_seat_conflict

    days, prev_end_time, new_end_time = _validate_leave_request(db, reservation, start_date, end_date)

    final_seat_id = target_seat_id or reservation.seat_id
    if final_seat_id == reservation.seat_id:
        conflict = find_seat_conflict(
            db,
            reservation.seat_id,
            prev_end_time,
            new_end_time,
            exclude_reservation_id=reservation.id,
        )
        if conflict:
            raise HTTPException(
                status_code=409,
                detail=f"顺延时段原座位已被订单 {conflict.order_no} 占用，请选择同店替代座位",
            )
    else:
        seat = db.get(Seat, final_seat_id)
        if not seat or seat.store_id != reservation.store_id or seat.status != 1:
            raise HTTPException(status_code=400, detail="所选替代座位不可用或不属于该门店")
        check_start = max(datetime.now(), reservation.start_time)
        conflict = find_seat_conflict(
            db,
            final_seat_id,
            check_start,
            new_end_time,
            exclude_reservation_id=reservation.id,
        )
        if conflict:
            raise HTTPException(
                status_code=409,
                detail=f"替代座位 {seat.seat_code} 在顺延期间已被订单 {conflict.order_no} 占用，请换选其他座位",
            )

    leave = ReservationLeave(
        reservation_id=reservation.id,
        period_card_id=reservation.period_card_id,
        user_id=reservation.user_id,
        store_id=reservation.store_id,
        start_date=start_date,
        end_date=end_date,
        days=days,
        status="active",
        prev_end_time=prev_end_time,
        new_end_time=new_end_time,
        original_seat_id=reservation.seat_id,
        target_seat_id=final_seat_id,
        reason=(reason or "").strip()[:200] or None,
        created_by_admin_id=admin.id,
    )
    db.add(leave)
    reservation.end_time = new_end_time
    if final_seat_id != reservation.seat_id:
        reservation.seat_id = final_seat_id

    log_admin_action(
        db,
        admin,
        action="reservation_leave_create",
        target_type="reservation",
        target_id=reservation.order_no,
        detail=(
            f"月卡请假 {start_date} 至 {end_date}（{days}天），"
            f"结束时间顺延至 {new_end_time.strftime('%Y-%m-%d %H:%M')}"
            + (f"，换座至 seat#{final_seat_id}" if final_seat_id != leave.original_seat_id else "")
        ),
    )
    db.commit()
    db.refresh(leave)
    db.refresh(reservation)
    return {
        "leave": _serialize_leave(db, leave),
        "used_count": count_used_leaves(db, reservation),
        "limit": MONTHLY_LEAVE_LIMIT,
        "new_end_time": reservation.end_time.strftime("%Y-%m-%d %H:%M"),
    }


def cancel_or_resume_monthly_leave(
    db: Session,
    leave: ReservationLeave,
    admin: AdminUser,
) -> dict:
    """取消未开始的请假（退回次数与顺延天数），或提前恢复进行中的请假。"""
    from app.services.business import find_seat_conflict

    if leave.status != "active":
        raise HTTPException(status_code=400, detail="该请假记录已取消")

    reservation = db.get(Reservation, leave.reservation_id)
    if not reservation:
        raise HTTPException(status_code=404, detail="关联预约订单不存在")

    today = datetime.now().date()
    if today > leave.end_date:
        raise HTTPException(status_code=400, detail="该次请假已结束，无法取消")

    # 确定要恢复使用的日期区间（检查原座是否已被他人约走）
    if today <= leave.start_date:
        # 尚未开始或当天起请假：整次撤销，退回次数和全部顺延天数
        resume_start = max(datetime.now(), datetime.combine(leave.start_date, datetime.min.time()))
        resume_end = datetime.combine(leave.end_date, datetime.max.time().replace(microsecond=0))
        conflict = find_seat_conflict(
            db,
            reservation.seat_id,
            resume_start,
            resume_end,
            exclude_reservation_id=reservation.id,
        )
        if conflict:
            raise HTTPException(
                status_code=409,
                detail=f"原座位在 {leave.start_date} 至 {leave.end_date} 已被订单 {conflict.order_no} 预约，无法直接取消请假",
            )
        rollback_days = leave.days
        leave.status = "cancelled"
        leave.cancelled_at = datetime.now()
        reservation.end_time = reservation.end_time - timedelta(days=rollback_days)
        action_msg = f"撤销请假 {leave.start_date} 至 {leave.end_date}，扣回顺延 {rollback_days} 天并退回 1 次请假额度"
    else:
        # 进行中（start_date < today <= end_date）：提前从今日起恢复，保留已休天数
        resume_start = datetime.now()
        resume_end = datetime.combine(leave.end_date, datetime.max.time().replace(microsecond=0))
        conflict = find_seat_conflict(
            db,
            reservation.seat_id,
            resume_start,
            resume_end,
            exclude_reservation_id=reservation.id,
        )
        if conflict:
            raise HTTPException(
                status_code=409,
                detail=f"原座位在今日至 {leave.end_date} 已被订单 {conflict.order_no} 预约，暂无法提前恢复",
            )
        new_end_date = today - timedelta(days=1)
        actual_days = (new_end_date - leave.start_date).days + 1
        rollback_days = leave.days - actual_days
        leave.end_date = new_end_date
        leave.days = actual_days
        reservation.end_time = reservation.end_time - timedelta(days=rollback_days)
        leave.new_end_time = reservation.end_time
        action_msg = f"提前恢复请假（实际休假 {leave.start_date} 至 {new_end_date}，共 {actual_days} 天），扣回多余顺延 {rollback_days} 天"

    log_admin_action(
        db,
        admin,
        action="reservation_leave_cancel",
        target_type="reservation",
        target_id=reservation.order_no,
        detail=action_msg,
    )
    db.commit()
    db.refresh(leave)
    db.refresh(reservation)
    return {
        "message": action_msg,
        "leave": _serialize_leave(db, leave),
        "used_count": count_used_leaves(db, reservation),
        "limit": MONTHLY_LEAVE_LIMIT,
        "new_end_time": reservation.end_time.strftime("%Y-%m-%d %H:%M"),
    }
