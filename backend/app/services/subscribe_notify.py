"""微信订阅消息：期限卡到期、预约确认、即将到期提醒、离座结算通知。"""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
import logging
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.redis_client import cache_get, cache_set
from app.models import CardType, PeriodCard, Reservation, Seat, Store, User, WechatSubscription
from app.services.business import WechatService
from app.services.card_service import is_period_card_active

logger = logging.getLogger(__name__)

CARD_EXPIRE_SCENE = "card_expire"
BOOKING_CONFIRM_SCENE = "booking_confirm"
EXPIRING_SOON_SCENE = "expiring_soon"
CHECKOUT_SCENE = "checkout"
REMIND_DAYS_BEFORE = 5


def _run_async(coro):
    """安全执行协程：若当前线程已有运行中的事件循环，则在独立线程中执行。"""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


def is_long_period_card(card: PeriodCard) -> bool:
    """月卡 / 双月卡 / 季卡（含夜读月卡）；排除天卡、次卡、小时卡。"""
    if card.card_type in (CardType.monthly, CardType.quarterly, CardType.night_monthly):
        return True
    name = card.card_name or ""
    if any(k in name for k in ("双月", "季卡", "月卡", "通宵月")):
        if "天卡" in name or "次卡" in name:
            return False
        return True
    if card.start_date and card.end_date:
        days = (card.end_date - card.start_date).days + 1
        return days >= 28
    return False


def _card_type_label(card: PeriodCard) -> str:
    name = (card.card_name or "").strip()
    if name:
        return name[:20]
    mapping = {
        CardType.monthly: "月卡",
        CardType.quarterly: "季卡",
        CardType.night_monthly: "夜读月卡",
    }
    return mapping.get(card.card_type, "期限卡")


def _build_template_data(card: PeriodCard) -> dict:
    """字段与模板「订阅服务续费提醒」一致：thing6=服务名称，time3=到期时间。"""
    end = card.end_date.isoformat() if card.end_date else ""
    return {
        "thing6": {"value": _card_type_label(card)[:20]},
        "time3": {"value": end},
    }


def _latest_accept_subscription(
    db: Session, user_id: int, tmpl_id: str
) -> WechatSubscription | None:
    return db.scalar(
        select(WechatSubscription)
        .where(
            WechatSubscription.user_id == user_id,
            WechatSubscription.tmpl_id == tmpl_id,
            WechatSubscription.status == 1,
        )
        .order_by(WechatSubscription.id.desc())
    )


def _has_accept_subscription(db: Session, user_id: int, tmpl_id: str) -> bool:
    return _latest_accept_subscription(db, user_id, tmpl_id) is not None


def _send_and_consume(
    db: Session,
    *,
    user: User,
    tmpl_id: str,
    data: dict,
    page: str,
) -> bool:
    """发送一次性订阅消息，成功后将订阅记录置为已消费 (status=0)。"""
    if not tmpl_id or not user or not user.openid:
        return False
    sub = _latest_accept_subscription(db, user.id, tmpl_id)
    if not sub:
        return False
    _run_async(
        WechatService.send_subscribe_message(
            openid=user.openid,
            template_id=tmpl_id,
            data=data,
            page=page,
        )
    )
    sub.status = 0
    return True


def _reservation_location_label(db: Session, reservation: Reservation) -> str:
    store = db.get(Store, reservation.store_id)
    seat = db.get(Seat, reservation.seat_id)
    store_name = (store.name if store else "知行岛自习室").strip()
    seat_code = (seat.seat_code if seat else "").strip()
    label = f"{store_name} {seat_code}".strip()
    return label[:20]


def send_booking_confirm_notify(db: Session, reservation: Reservation) -> bool:
    """预约支付成功后发送预约确认订阅消息。"""
    tmpl_id = (settings.wx_subscribe_booking_confirm_tmpl_id or "").strip()
    if not tmpl_id:
        return False
    user = db.get(User, reservation.user_id)
    if not user or not user.openid:
        return False
    time_range = (
        f"{reservation.start_time.strftime('%m-%d %H:%M')}"
        f"~{reservation.end_time.strftime('%H:%M')}"
    )
    data = {
        "thing1": {"value": _reservation_location_label(db, reservation)},
        "time2": {"value": reservation.start_time.strftime("%Y-%m-%d %H:%M")},
        "thing3": {"value": f"时段 {time_range}"[:20]},
    }
    try:
        return _send_and_consume(
            db,
            user=user,
            tmpl_id=tmpl_id,
            data=data,
            page="pages/orders/index",
        )
    except Exception as exc:
        logger.warning(
            "booking confirm notify failed res=%s user=%s: %s",
            reservation.id,
            user.id,
            exc,
        )
        return False


def remind_expiring_reservations(db: Session, *, now: datetime | None = None) -> dict:
    """扫描 15~30 分钟内即将结束的预约并发送续时/离座提醒（Redis 去重）。"""
    tmpl_id = (settings.wx_subscribe_expiring_soon_tmpl_id or "").strip()
    if not tmpl_id:
        return {"skipped": True, "reason": "no_tmpl", "sent": 0}

    now = now or datetime.now()
    win_start = now + timedelta(minutes=15)
    win_end = now + timedelta(minutes=30)
    rows = db.scalars(
        select(Reservation).where(
            Reservation.pay_status == 1,
            Reservation.status.in_([0, 1]),
            Reservation.end_time > win_start,
            Reservation.end_time <= win_end,
        )
    ).all()

    sent = 0
    failed = 0
    for res in rows:
        dedup_key = f"res_exp_reminded:{res.id}"
        if cache_get(dedup_key):
            continue
        user = db.get(User, res.user_id)
        if not user or not user.openid:
            continue
        sub = _latest_accept_subscription(db, user.id, tmpl_id)
        if not sub:
            continue
        data = {
            "thing1": {"value": _reservation_location_label(db, res)},
            "time2": {"value": res.end_time.strftime("%Y-%m-%d %H:%M")},
            "thing3": {"value": "即将结束，可在线续时或整理离座"[:20]},
        }
        try:
            _run_async(
                WechatService.send_subscribe_message(
                    openid=user.openid,
                    template_id=tmpl_id,
                    data=data,
                    page="pages/orders/index",
                )
            )
            sub.status = 0
            cache_set(dedup_key, "1", 7200)
            sent += 1
        except Exception as exc:
            failed += 1
            logger.warning(
                "expiring reservation remind failed res=%s user=%s: %s",
                res.id,
                user.id,
                exc,
            )

    if sent or failed:
        db.commit()
    return {"sent": sent, "failed": failed}


def send_checkout_notify(db: Session, reservation: Reservation) -> bool:
    """预约结束自动/手动离座后发送结算通知。"""
    tmpl_id = (settings.wx_subscribe_checkout_tmpl_id or "").strip()
    if not tmpl_id:
        return False
    user = db.get(User, reservation.user_id)
    if not user or not user.openid:
        return False
    end_dt = reservation.actual_end_time or reservation.end_time or datetime.now()
    data = {
        "thing1": {"value": _reservation_location_label(db, reservation)},
        "time2": {"value": end_dt.strftime("%Y-%m-%d %H:%M")},
        "thing3": {"value": "自习已结束，欢迎下次再来"[:20]},
    }
    try:
        return _send_and_consume(
            db,
            user=user,
            tmpl_id=tmpl_id,
            data=data,
            page="pages/orders/index",
        )
    except Exception as exc:
        logger.warning(
            "checkout notify failed res=%s user=%s: %s",
            reservation.id,
            user.id,
            exc,
        )
        return False


def remind_expiring_period_cards(db: Session, *, today: date | None = None) -> dict:
    """扫描还剩 5 天到期的长期卡并发送订阅消息。"""
    tmpl_id = (settings.wx_subscribe_card_expire_tmpl_id or "").strip()
    if not tmpl_id:
        logger.info("card expire remind skipped: tmpl id not configured")
        return {"skipped": True, "reason": "no_tmpl", "sent": 0}

    today = today or date.today()
    target = today + timedelta(days=REMIND_DAYS_BEFORE)
    cards = db.scalars(
        select(PeriodCard).where(
            PeriodCard.status == 1,
            PeriodCard.end_date == target,
            PeriodCard.expire_reminded_at.is_(None),
        )
    ).all()

    sent = 0
    failed = 0
    for card in cards:
        if not is_long_period_card(card):
            continue
        if not is_period_card_active(card, today):
            continue
        user = db.get(User, card.user_id)
        if not user or not user.openid:
            continue
        sub = _latest_accept_subscription(db, user.id, tmpl_id)
        if not sub:
            continue

        try:
            _run_async(
                WechatService.send_subscribe_message(
                    openid=user.openid,
                    template_id=tmpl_id,
                    data=_build_template_data(card),
                    page="pages/packages/index",
                )
            )
            sub.status = 0
            card.expire_reminded_at = datetime.now()
            sent += 1
        except Exception as exc:
            failed += 1
            logger.warning(
                "card expire remind failed card=%s user=%s: %s",
                card.id,
                user.id,
                exc,
            )

    if sent or failed:
        db.commit()
    return {"sent": sent, "failed": failed, "target_date": str(target)}
