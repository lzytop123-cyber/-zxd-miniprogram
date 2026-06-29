import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import select

from app.core.redis_client import get_redis
from app.db.session import SessionLocal
from app.models import BleBatteryAlert, BleLock, Reservation
from app.services.booking import auto_checkin_due_batch, finalize_expired_reservation

logger = logging.getLogger(__name__)

BATTERY_LOW_THRESHOLD = 20

# 多 worker 部署时，仅由抢到分布式锁的实例运行定时任务，避免重复执行
_LEADER_LOCK_KEY = "zxd:scheduler:leader"
_LEADER_TTL_SECONDS = 120
_scheduler: BackgroundScheduler | None = None


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
        changed = False
        for r in rows:
            if finalize_expired_reservation(db, r, now):
                changed = True
        if changed:
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


def auto_checkin_due_orders():
    db = SessionLocal()
    try:
        auto_checkin_due_batch(db)
    finally:
        db.close()


def health_alert_job():
    db = SessionLocal()
    try:
        from app.services.health_alert import maybe_send_health_alert

        maybe_send_health_alert(db)
    finally:
        db.close()


def _acquire_leadership() -> bool:
    """抢占调度领导权（分布式锁）。抢到的实例负责跑定时任务。"""
    client = get_redis()
    try:
        return bool(client.set(_LEADER_LOCK_KEY, "1", nx=True, ex=_LEADER_TTL_SECONDS))
    except Exception:
        # Redis 不可用时退化为本进程运行（单实例部署可接受）
        logger.warning("scheduler: 获取领导权锁失败，退化为本进程运行", exc_info=True)
        return True


def _renew_leadership():
    """周期性续约领导权，避免锁过期后无人调度。"""
    client = get_redis()
    try:
        client.set(_LEADER_LOCK_KEY, "1", ex=_LEADER_TTL_SECONDS)
    except Exception:
        logger.warning("scheduler: 续约领导权失败", exc_info=True)


def start_scheduler():
    global _scheduler
    if _scheduler is not None:
        return
    if not _acquire_leadership():
        logger.info("scheduler: 未抢到领导权，跳过定时任务启动（多 worker 部署）")
        return

    scheduler = BackgroundScheduler()
    scheduler.add_job(_renew_leadership, "interval", seconds=_LEADER_TTL_SECONDS // 2)
    scheduler.add_job(cancel_unpaid_orders, "interval", minutes=5)
    scheduler.add_job(expire_finished_orders, "interval", minutes=5)
    scheduler.add_job(auto_checkin_due_orders, "interval", minutes=1)
    scheduler.add_job(check_ble_battery, "interval", hours=1)
    scheduler.add_job(health_alert_job, "interval", minutes=5)
    scheduler.start()
    _scheduler = scheduler
    logger.info("scheduler: 已启动定时任务")
