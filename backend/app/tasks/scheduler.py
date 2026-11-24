import logging
from datetime import datetime, timedelta
from uuid import uuid4

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import select

from app.core.config import settings
from app.core.redis_client import MemoryRedis
from app.db.session import SessionLocal
from app.models import BleBatteryAlert, BleLock, Reservation
from app.services.booking import auto_checkin_due_batch, finalize_expired_reservation
from app.services.coupon_service import refund_coupon_for_reservation

logger = logging.getLogger(__name__)

BATTERY_LOW_THRESHOLD = 20

# 多 worker 部署时，仅由抢到分布式锁的实例运行定时任务，避免重复执行
_LEADER_LOCK_KEY = "zxd:scheduler:leader"
_LEADER_TTL_SECONDS = 120
_scheduler: BackgroundScheduler | None = None
_leader_client = None
_owner_token = uuid4().hex
_has_leadership = False

_RENEW_LEASE = """
if redis.call('get', KEYS[1]) == ARGV[1] then
    return redis.call('expire', KEYS[1], ARGV[2])
end
return 0
"""
_RELEASE_LEASE = """
if redis.call('get', KEYS[1]) == ARGV[1] then
    return redis.call('del', KEYS[1])
end
return 0
"""


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
            # Payment callbacks lock the same order; re-read after acquiring it.
            db.refresh(r, with_for_update=True)
            if r.pay_status != 0 or r.status != 0:
                continue
            r.status = 3
            refund_coupon_for_reservation(db, r)
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


def remind_card_expire_job():
    db = SessionLocal()
    try:
        from app.services.subscribe_notify import remind_expiring_period_cards

        result = remind_expiring_period_cards(db)
        if result.get("sent") or result.get("failed"):
            logger.info("card expire remind: %s", result)
    except Exception:
        logger.exception("card expire remind job failed")
    finally:
        db.close()


def _acquire_leadership() -> bool:
    """抢占调度领导权（分布式锁）。抢到的实例负责跑定时任务。"""
    try:
        client = _get_leader_redis()
        if isinstance(client, MemoryRedis):
            return False
        return bool(client.set(_LEADER_LOCK_KEY, _owner_token, nx=True, ex=_LEADER_TTL_SECONDS))
    except Exception:
        logger.warning("scheduler: Redis 不可用，暂停任务并等待重试", exc_info=True)
        return False


def _get_leader_redis():
    # The shared cache client can fall back to process-local memory. A lease must
    # always use Redis; its connection pool reconnects when Redis recovers.
    global _leader_client
    if _leader_client is None:
        import redis

        _leader_client = redis.from_url(
            settings.redis_url, decode_responses=True,
            socket_connect_timeout=1, socket_timeout=1,
        )
    return _leader_client


def _renew_leadership():
    """周期性续约领导权，避免锁过期后无人调度。"""
    try:
        return bool(_get_leader_redis().eval(
            _RENEW_LEASE, 1, _LEADER_LOCK_KEY, _owner_token, _LEADER_TTL_SECONDS,
        ))
    except Exception:
        logger.warning("scheduler: 续约领导权失败", exc_info=True)
        return False


def _maintain_leadership():
    global _has_leadership
    if _has_leadership and _renew_leadership():
        return
    _has_leadership = _acquire_leadership()


def _run_as_leader(job):
    global _has_leadership
    if _has_leadership:
        _has_leadership = _renew_leadership()
        if _has_leadership:
            return job()


def start_scheduler():
    global _scheduler, _owner_token
    if _scheduler is not None:
        return
    _owner_token = uuid4().hex
    _maintain_leadership()
    scheduler = BackgroundScheduler()
    scheduler.add_job(_maintain_leadership, "interval", seconds=30)
    scheduler.add_job(_run_as_leader, "interval", args=[cancel_unpaid_orders], minutes=5)
    scheduler.add_job(_run_as_leader, "interval", args=[expire_finished_orders], minutes=5)
    scheduler.add_job(_run_as_leader, "interval", args=[auto_checkin_due_orders], minutes=1)
    scheduler.add_job(_run_as_leader, "interval", args=[check_ble_battery], hours=1)
    scheduler.add_job(_run_as_leader, "interval", args=[health_alert_job], minutes=5)
    scheduler.add_job(_run_as_leader, "cron", args=[remind_card_expire_job], hour=10, minute=0)
    scheduler.start()
    _scheduler = scheduler
    logger.info("scheduler: 已启动定时任务")


def stop_scheduler():
    global _scheduler, _has_leadership
    if _scheduler is None:
        return
    _scheduler.shutdown(wait=True)
    _scheduler = None
    _has_leadership = False
    try:
        _get_leader_redis().eval(_RELEASE_LEASE, 1, _LEADER_LOCK_KEY, _owner_token)
    except Exception:
        logger.warning("scheduler: 释放领导权失败，等待锁自动过期", exc_info=True)
