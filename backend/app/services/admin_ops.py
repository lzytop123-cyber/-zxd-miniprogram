"""后台运营操作：发券、订单客服、远程开门等。"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import (
    BleKey,
    BleLock,
    CardPurchaseOrder,
    CardSource,
    CardType,
    Coupon,
    DoorLog,
    MeituanOrder,
    OpenType,
    PeriodCard,
    PointLog,
    RechargeOrder,
    Reservation,
    RewardType,
    StudyStat,
    User,
    WalletLog,
    WechatSubscription,
)
from app.services.booking import auto_checkin_reservation, record_study_on_checkout, reservation_unlock_allowed
from app.services.business import TTLockService
from app.services.card_service import (
    card_validity_api_fields,
    is_office_night_monthly_card,
    issue_period_card,
)
from app.services.store_hours import OFFICE_NIGHT_USAGE_RULE

CARD_TYPE_LABELS = {
    CardType.hourly: "小时卡",
    CardType.daily: "天卡",
    CardType.weekly: "周卡",
    CardType.monthly: "月卡",
    CardType.quarterly: "季卡",
    CardType.session: "次卡",
    CardType.night_monthly: "夜读月卡",
}

CARD_TYPE_TO_REWARD: dict[CardType, RewardType] = {
    CardType.hourly: RewardType.hours,
    CardType.daily: RewardType.day_pass,
    CardType.weekly: RewardType.week_pass,
    CardType.monthly: RewardType.month_pass,
    CardType.quarterly: RewardType.quarter_pass,
    CardType.session: RewardType.session,
    CardType.night_monthly: RewardType.night_monthly,
}


def period_card_admin_dict(db: Session, card: PeriodCard, today: date | None = None) -> dict:
    today = today or date.today()
    user = db.get(User, card.user_id)
    validity = card_validity_api_fields(card, today)
    return {
        "id": card.id,
        "user_id": card.user_id,
        "user_nickname": user.nickname if user else None,
        "user_phone": user.phone if user else None,
        "store_id": card.store_id,
        "card_name": card.card_name,
        "card_type": card.card_type.value,
        "remaining_hours": float(card.remaining_hours) if card.remaining_hours is not None else None,
        "total_hours": float(card.total_hours) if card.total_hours is not None else None,
        "remaining_sessions": card.remaining_sessions,
        "total_sessions": card.total_sessions,
        "start_date": str(card.start_date) if card.start_date else None,
        "end_date": str(card.end_date) if card.end_date else None,
        **validity,
        "usage_rule": OFFICE_NIGHT_USAGE_RULE if is_office_night_monthly_card(card) else None,
        "source": card.source.value if card.source else None,
        "status": card.status,
        "remark": card.remark,
        "created_at": card.created_at.isoformat() if card.created_at else None,
    }


def issue_admin_period_card(
    db: Session,
    *,
    user_id: int,
    card_type: CardType,
    reward_value: int,
    store_id: int | None = None,
    card_name: str | None = None,
    remark: str | None = None,
) -> PeriodCard:
    user = db.get(User, user_id)
    if not user:
        raise ValueError("用户不存在")
    reward_type = CARD_TYPE_TO_REWARD.get(card_type)
    if not reward_type:
        raise ValueError("不支持的卡类型")

    label = card_name or CARD_TYPE_LABELS.get(card_type, card_type.value)
    mapping = SimpleNamespace(
        deal_name=label,
        reward_type=reward_type,
        reward_value=reward_value,
        store_id=store_id,
        night_start=None,
        night_end=None,
    )
    card = issue_period_card(
        db,
        user_id,
        mapping,
        CardSource.admin,
        receipt=f"admin-{uuid.uuid4().hex[:12]}",
        store_id=store_id,
    )
    if remark:
        card.remark = remark
    return card


def update_admin_period_card(
    db: Session,
    card: PeriodCard,
    *,
    status: int | None = None,
    end_date: date | None = None,
    extend_days: int | None = None,
    remaining_hours: Decimal | None = None,
    total_hours: Decimal | None = None,
    remaining_sessions: int | None = None,
    remark: str | None = None,
) -> PeriodCard:
    if status is not None:
        card.status = status
    if end_date is not None:
        card.end_date = end_date
    elif extend_days is not None and extend_days > 0:
        base = card.end_date or date.today()
        card.end_date = base + timedelta(days=extend_days)
    if remaining_hours is not None:
        card.remaining_hours = remaining_hours
    if total_hours is not None:
        card.total_hours = total_hours
    if remaining_sessions is not None:
        card.remaining_sessions = remaining_sessions
    if remark is not None:
        card.remark = remark
    return card


async def admin_remote_unlock(db: Session, reservation: Reservation) -> dict:
    if not settings.ttlock_remote_unlock_enabled:
        raise ValueError("门店门锁不支持远程开门")
    if reservation.pay_status != 1:
        raise ValueError("订单未支付")
    if not reservation_unlock_allowed(reservation):
        raise ValueError("不在开门时段或订单已结束")

    ble_key = db.scalar(
        select(BleKey).where(
            BleKey.reservation_id == reservation.id,
            BleKey.user_id == reservation.user_id,
            BleKey.status == 1,
        )
    )
    if not ble_key:
        raise ValueError("蓝牙钥匙未生成，请确认订单已支付且门锁已配置")

    lock = db.get(BleLock, ble_key.lock_id)
    if not lock or not lock.lock_id:
        raise ValueError("门店未配置门锁")

    if str(lock.lock_id).startswith("mock_"):
        result = {"mock": True}
    else:
        result = await TTLockService.remote_unlock(str(lock.lock_id))

    log = DoorLog(
        lock_id=ble_key.lock_id,
        user_id=reservation.user_id,
        reservation_id=reservation.id,
        open_type=OpenType.remote,
        result=1,
    )
    ble_key.used_at = datetime.now()
    auto_checkin_reservation(db, reservation)
    db.add(log)
    return {"result": result, "lock_name": lock.lock_name}


def admin_force_checkout(db: Session, reservation: Reservation) -> None:
    if reservation.status not in (0, 1):
        raise ValueError("当前订单状态不可强制离座")
    reservation.status = 2
    reservation.actual_end_time = datetime.now()
    user = db.get(User, reservation.user_id)
    if user:
        record_study_on_checkout(db, reservation, user)


def user_overview(db: Session, user_id: int) -> dict:
    user = db.get(User, user_id)
    if not user:
        raise ValueError("用户不存在")

    from app.api.routes.reservation import _safe_to_item
    from app.services.card_service import repair_misissued_card_validity

    orders = db.scalars(
        select(Reservation)
        .where(Reservation.user_id == user_id)
        .order_by(Reservation.created_at.desc())
        .limit(20)
    ).all()
    cards = db.scalars(
        select(PeriodCard)
        .where(PeriodCard.user_id == user_id)
        .order_by(PeriodCard.created_at.desc())
        .limit(20)
    ).all()
    exchanges = db.scalars(
        select(MeituanOrder)
        .where(MeituanOrder.user_id == user_id)
        .order_by(MeituanOrder.created_at.desc())
        .limit(20)
    ).all()
    wallet_logs = db.scalars(
        select(WalletLog)
        .where(WalletLog.user_id == user_id)
        .order_by(WalletLog.created_at.desc())
        .limit(20)
    ).all()

    today = date.today()
    repaired = False
    card_items = []
    for c in cards:
        if repair_misissued_card_validity(c):
            repaired = True
        card_items.append(period_card_admin_dict(db, c, today))
    if repaired:
        db.commit()

    order_items = []
    for r in orders:
        item = _safe_to_item(db, r)
        if not item:
            continue
        order_items.append(
            {
                **item.model_dump(),
                "pay_type": r.pay_type.value if r.pay_type else None,
            }
        )

    return {
        "orders": order_items,
        "cards": card_items,
        "exchanges": [
            {
                "id": e.id,
                "coupon_code": e.coupon_code,
                "deal_name": e.deal_name,
                "status": e.status.value if e.status else None,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in exchanges
        ],
        "wallet_logs": [
            {
                "id": w.id,
                "type": w.type,
                "amount": float(w.amount),
                "remark": w.remark,
                "created_at": w.created_at.isoformat() if w.created_at else None,
            }
            for w in wallet_logs
        ],
        "ttlock_configured": bool(settings.ttlock_client_id and settings.ttlock_client_secret),
    }


def delete_user_cascade(db: Session, user_id: int) -> dict:
    """永久删除用户及其关联业务数据。返回被删用户摘要。"""
    user = db.get(User, user_id)
    if not user:
        raise ValueError("用户不存在")

    summary = {
        "id": user.id,
        "nickname": user.nickname,
        "phone": user.phone,
        "openid": user.openid,
    }

    reservation_ids = list(
        db.scalars(select(Reservation.id).where(Reservation.user_id == user_id)).all()
    )

    # 解除其他用户「被此人邀请」的引用
    db.execute(update(User).where(User.invited_by == user_id).values(invited_by=None))

    if reservation_ids:
        db.execute(delete(BleKey).where(BleKey.reservation_id.in_(reservation_ids)))
        db.execute(
            update(DoorLog)
            .where(DoorLog.reservation_id.in_(reservation_ids))
            .values(reservation_id=None, user_id=None)
        )

    db.execute(delete(BleKey).where(BleKey.user_id == user_id))
    db.execute(update(DoorLog).where(DoorLog.user_id == user_id).values(user_id=None))

    # 预约可能引用期限卡，先断开再删预约
    db.execute(
        update(Reservation).where(Reservation.user_id == user_id).values(period_card_id=None)
    )
    db.execute(delete(Reservation).where(Reservation.user_id == user_id))

    # 购卡订单可能引用期限卡
    db.execute(
        update(CardPurchaseOrder)
        .where(CardPurchaseOrder.user_id == user_id)
        .values(period_card_id=None)
    )
    db.execute(delete(CardPurchaseOrder).where(CardPurchaseOrder.user_id == user_id))
    db.execute(delete(PeriodCard).where(PeriodCard.user_id == user_id))

    db.execute(delete(RechargeOrder).where(RechargeOrder.user_id == user_id))
    db.execute(delete(Coupon).where(Coupon.user_id == user_id))
    db.execute(delete(WalletLog).where(WalletLog.user_id == user_id))
    db.execute(delete(PointLog).where(PointLog.user_id == user_id))
    db.execute(delete(StudyStat).where(StudyStat.user_id == user_id))
    db.execute(delete(WechatSubscription).where(WechatSubscription.user_id == user_id))
    db.execute(update(MeituanOrder).where(MeituanOrder.user_id == user_id).values(user_id=None))

    db.delete(user)
    return summary
