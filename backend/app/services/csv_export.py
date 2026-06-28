"""后台 CSV 导出。"""

from __future__ import annotations

import csv
import io
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Reservation, StudyStat, User, WalletLog


def _csv_response(filename: str, rows: list[list], header: list[str]) -> tuple[str, str]:
    buf = io.StringIO()
    buf.write("\ufeff")
    writer = csv.writer(buf)
    writer.writerow(header)
    writer.writerows(rows)
    return filename, buf.getvalue()


def export_reservations_csv(
    db: Session,
    *,
    store_id: int | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
) -> tuple[str, str]:
    query = select(Reservation)
    if store_id:
        query = query.where(Reservation.store_id == store_id)
    if start:
        query = query.where(Reservation.created_at >= start)
    if end:
        query = query.where(Reservation.created_at <= end)
    rows_db = db.scalars(query.order_by(Reservation.created_at.desc()).limit(10000)).all()

    rows: list[list] = []
    for r in rows_db:
        user = db.get(User, r.user_id)
        rows.append([
            r.order_no,
            r.user_id,
            user.nickname if user else "",
            user.phone if user else "",
            r.store_id,
            r.seat_id,
            r.bill_type.value,
            float(r.final_price or 0),
            r.pay_status,
            r.status,
            r.pay_type.value if r.pay_type else "",
            r.refund_remark or "",
            r.refunded_at.isoformat() if r.refunded_at else "",
            r.start_time.isoformat() if r.start_time else "",
            r.end_time.isoformat() if r.end_time else "",
            r.created_at.isoformat() if r.created_at else "",
        ])
    return _csv_response(
        "reservations.csv",
        rows,
        [
            "订单号", "用户ID", "昵称", "手机号", "门店ID", "座位ID", "计费类型",
            "实付金额", "支付状态", "订单状态", "支付方式", "退款备注", "退款时间",
            "开始时间", "结束时间", "创建时间",
        ],
    )


def export_wallet_logs_csv(db: Session, *, user_id: int | None = None) -> tuple[str, str]:
    query = select(WalletLog)
    if user_id:
        query = query.where(WalletLog.user_id == user_id)
    rows_db = db.scalars(query.order_by(WalletLog.created_at.desc()).limit(10000)).all()
    rows = []
    for log in rows_db:
        user = db.get(User, log.user_id)
        rows.append([
            log.id,
            log.user_id,
            user.nickname if user else "",
            log.type,
            float(log.amount or 0),
            float(log.balance_after or 0),
            log.remark or "",
            log.created_at.isoformat() if log.created_at else "",
        ])
    return _csv_response(
        "wallet_logs.csv",
        rows,
        ["ID", "用户ID", "昵称", "类型", "金额", "余额后", "备注", "时间"],
    )


def export_study_stats_csv(db: Session) -> tuple[str, str]:
    rows_db = db.scalars(
        select(StudyStat).order_by(StudyStat.stat_date.desc()).limit(10000)
    ).all()
    rows = []
    for s in rows_db:
        user = db.get(User, s.user_id)
        rows.append([
            s.user_id,
            user.nickname if user else "",
            s.store_id or "",
            s.stat_date.isoformat() if s.stat_date else "",
            s.total_minutes or 0,
            s.session_count or 0,
        ])
    return _csv_response(
        "study_stats.csv",
        rows,
        ["用户ID", "昵称", "门店ID", "日期", "学习分钟", "会话数"],
    )
