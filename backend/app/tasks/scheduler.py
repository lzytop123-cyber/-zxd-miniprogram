from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import BleBatteryAlert, BleLock, Reservation

BATTERY_LOW_THRESHOLD = 20


def cancel_unpaid_orders():
    db = SessionLocal()
    try:
        cutoff = datetime.now() - timedelta(minutes=15)
        rows = db.scalars(
            select(Reservation).where(
                Reservation.pay_status == 0,
                Reservation.status == 0,
                Reservation.created_at < cutoff,
            )
        ).all()
        for r in rows:
            r.status = 3
        db.commit()
    finally:
        db.close()


def expire_finished_orders():
    db = SessionLocal()
    try:
        now = datetime.now()
        rows = db.scalars(
            select(Reservation).where(
                Reservation.status.in_([0, 1]),
                Reservation.end_time <= now,
            )
        ).all()
        for r in rows:
            if r.status == 1:
                r.status = 2
                r.actual_end_time = r.end_time
            elif r.status == 0:
                r.status = 3
        db.commit()
    finally:
        db.close()


def check_ble_battery():
    db = SessionLocal()
    try:
        locks = db.scalars(select(BleLock).where(BleLock.status == 1)).all()
        for lock in locks:
            level = lock.battery_level
            if level is None or level >= BATTERY_LOW_THRESHOLD:
                continue
            recent = db.scalar(
                select(BleBatteryAlert)
                .where(
                    BleBatteryAlert.lock_id == lock.id,
                    BleBatteryAlert.is_read == 0,
                )
                .order_by(BleBatteryAlert.created_at.desc())
            )
            if recent:
                continue
            db.add(
                BleBatteryAlert(
                    lock_id=lock.id,
                    battery_level=level,
                    message=f"{lock.lock_name or '门锁'} 电量 {level}%，请及时更换电池",
                )
            )
        db.commit()
    finally:
        db.close()


def start_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(cancel_unpaid_orders, "interval", minutes=5)
    scheduler.add_job(expire_finished_orders, "interval", minutes=5)
    scheduler.add_job(check_ble_battery, "interval", hours=1)
    scheduler.start()
