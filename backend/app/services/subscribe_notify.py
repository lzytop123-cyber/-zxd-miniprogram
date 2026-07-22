"""期限卡到期订阅消息：扫描 + 发送。"""

from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import CardType, PeriodCard, User, WechatSubscription
from app.services.business import WechatService
from app.services.card_service import is_period_card_active

logger = logging.getLogger(__name__)

CARD_EXPIRE_SCENE = "card_expire"
REMIND_DAYS_BEFORE = 5


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
    """字段名需与微信后台模板一致；默认 thing1/time2/thing3，可按模板改。"""
    end = card.end_date.isoformat() if card.end_date else ""
    tip = "还剩5天到期，续费可继续预约座位"
    return {
        "thing1": {"value": _card_type_label(card)},
        "time2": {"value": end},
        "thing3": {"value": tip[:20]},
    }


def _has_accept_subscription(db: Session, user_id: int, tmpl_id: str) -> bool:
    row = db.scalar(
        select(WechatSubscription)
        .where(
            WechatSubscription.user_id == user_id,
            WechatSubscription.tmpl_id == tmpl_id,
            WechatSubscription.status == 1,
        )
        .order_by(WechatSubscription.id.desc())
    )
    return row is not None


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
        if not _has_accept_subscription(db, user.id, tmpl_id):
            continue

        try:
            asyncio.run(
                WechatService.send_subscribe_message(
                    openid=user.openid,
                    template_id=tmpl_id,
                    data=_build_template_data(card),
                    page="pages/packages/index",
                )
            )
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
