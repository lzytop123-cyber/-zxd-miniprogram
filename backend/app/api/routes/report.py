from datetime import date, datetime, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.prod import block_mock_in_production
from app.db.session import get_db
from app.models import PeriodCard, RechargeOrder, Reservation, Seat, StudyStat, User, WalletLog
from app.schemas.common import ResponseModel
from app.schemas.report import DailyStatItem, LeaderboardItem, ReportSummary, RechargeRequest, WalletInfo
from app.services.booking import add_wallet_log, fulfill_recharge_order
from app.services.card_service import daily_pass_days, is_period_card_active
from app.services.wechat_pay import WechatPayService

router = APIRouter(tags=["学习报告"])


def _mask_nickname(name: str | None) -> str:
    if not name:
        return "学员"
    if len(name) <= 2:
        return name[0] + "*"
    return name[0] + "*" * (len(name) - 2) + name[-1]


@router.get("/report/summary", response_model=ResponseModel[ReportSummary])
def report_summary(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    total_minutes = int(
        db.scalar(select(func.coalesce(func.sum(StudyStat.total_minutes), 0)).where(StudyStat.user_id == user.id))
        or 0
    )
    total_sessions = int(
        db.scalar(select(func.coalesce(func.sum(StudyStat.session_count), 0)).where(StudyStat.user_id == user.id))
        or 0
    )
    days = db.scalar(
        select(func.count(func.distinct(StudyStat.stat_date))).where(StudyStat.user_id == user.id)
    ) or 1
    daily_avg = total_minutes // max(days, 1)

    all_users = db.execute(
        select(StudyStat.user_id, func.sum(StudyStat.total_minutes).label("mins"))
        .group_by(StudyStat.user_id)
        .order_by(func.sum(StudyStat.total_minutes).desc())
    ).all()
    rank = None
    beat_percent = 0.0
    if all_users:
        user_ids = [r.user_id for r in all_users]
        if user.id in user_ids:
            rank = user_ids.index(user.id) + 1
            if len(all_users) > 1:
                beat_percent = round((len(all_users) - rank) / (len(all_users) - 1) * 100, 1)

    return ResponseModel(
        data=ReportSummary(
            total_sessions=total_sessions,
            total_minutes=total_minutes,
            total_hours=total_minutes // 60,
            total_minutes_remainder=total_minutes % 60,
            daily_avg_minutes=daily_avg,
            title=user.title or "小白",
            rank=rank,
            beat_percent=beat_percent,
        )
    )


@router.get("/report/daily", response_model=ResponseModel[list[DailyStatItem]])
def report_daily(
    days: int = Query(7, ge=1, le=90),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    since = date.today() - timedelta(days=days - 1)
    rows = db.scalars(
        select(StudyStat)
        .where(StudyStat.user_id == user.id, StudyStat.stat_date >= since)
        .order_by(StudyStat.stat_date)
    ).all()
    return ResponseModel(
        data=[
            DailyStatItem(stat_date=r.stat_date, total_minutes=r.total_minutes, session_count=r.session_count)
            for r in rows
        ]
    )


@router.get("/report/leaderboard", response_model=ResponseModel[list[LeaderboardItem]])
def leaderboard(
    store_id: int | None = None,
    limit: int = Query(50, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = select(
        StudyStat.user_id,
        func.sum(StudyStat.total_minutes).label("total_minutes"),
        func.sum(StudyStat.session_count).label("session_count"),
    ).group_by(StudyStat.user_id)
    if store_id:
        query = query.where(StudyStat.store_id == store_id)
    query = query.order_by(func.sum(StudyStat.total_minutes).desc()).limit(limit)
    rows = db.execute(query).all()

    user_ids = [row.user_id for row in rows]
    users = {
        u.id: u
        for u in (db.scalars(select(User).where(User.id.in_(user_ids))).all() if user_ids else [])
    }

    items: list[LeaderboardItem] = []
    for i, row in enumerate(rows, 1):
        u = users.get(row.user_id)
        items.append(
            LeaderboardItem(
                rank=i,
                nickname=_mask_nickname(u.nickname if u else None),
                title=u.title if u else "小白",
                total_minutes=int(row.total_minutes or 0),
                session_count=int(row.session_count or 0),
                is_self=u.id == user.id if u else False,
            )
        )
    return ResponseModel(data=items)


@router.get("/user/wallet", response_model=ResponseModel[WalletInfo])
def get_wallet(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    logs = db.scalars(
        select(WalletLog)
        .where(WalletLog.user_id == user.id)
        .order_by(WalletLog.created_at.desc())
        .limit(30)
    ).all()
    return ResponseModel(
        data=WalletInfo(
            balance=user.balance,
            logs=[
                {
                    "id": l.id,
                    "type": l.type,
                    "amount": float(l.amount or 0),
                    "balance_after": float(l.balance_after or 0),
                    "remark": l.remark,
                    "created_at": l.created_at.isoformat(),
                }
                for l in logs
            ],
        )
    )


@router.post("/user/recharge", response_model=ResponseModel)
def recharge(
    body: RechargeRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    order_no = f"RCH{datetime.now().strftime('%Y%m%d%H%M%S')}{user.id}"
    order = RechargeOrder(order_no=order_no, user_id=user.id, amount=body.amount, pay_status=0)
    db.add(order)
    db.commit()
    pay_params = WechatPayService.create_jsapi_order(
        order_no, body.amount, user.openid, f"知行岛余额充值-{body.amount}元"
    )
    return ResponseModel(
        data={"order_no": order_no, "wechat_pay": pay_params, "mock_recharge_url": f"/api/user/recharge/{order_no}/mock"}
    )


@router.post("/user/recharge/{order_no}/mock", response_model=ResponseModel[WalletInfo])
def mock_recharge(
    order_no: str,
    amount: Decimal = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """开发环境模拟充值成功（走与微信回调一致的幂等履约逻辑）"""
    block_mock_in_production()
    order = db.scalar(
        select(RechargeOrder).where(
            RechargeOrder.order_no == order_no, RechargeOrder.user_id == user.id
        )
    )
    if order is None:
        # 兼容历史无订单的调用：按传入金额补建订单
        order = RechargeOrder(
            order_no=order_no, user_id=user.id, amount=amount or Decimal("0"), pay_status=0
        )
        db.add(order)
        db.flush()
    fulfill_recharge_order(db, order)
    db.commit()
    db.refresh(user)
    return get_wallet(user, db)


@router.get("/user/cards", response_model=ResponseModel)
def get_cards(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    today = date.today()
    cards = db.scalars(
        select(PeriodCard)
        .where(PeriodCard.user_id == user.id, PeriodCard.status == 1)
        .order_by(PeriodCard.created_at.desc())
    ).all()
    active = []
    for c in cards:
        if not is_period_card_active(c, today):
            c.status = 0
            continue
        active.append(c)
    if len(active) < len(cards):
        db.commit()
    return ResponseModel(
        data=[
            {
                "id": c.id,
                "store_id": c.store_id,
                "card_name": c.card_name,
                "card_type": c.card_type.value,
                "remaining_hours": float(c.remaining_hours) if c.remaining_hours else None,
                "total_hours": float(c.total_hours) if c.total_hours else None,
                "remaining_sessions": c.remaining_sessions,
                "start_date": str(c.start_date) if c.start_date else None,
                "end_date": str(c.end_date) if c.end_date else None,
                "daily_pass_days": daily_pass_days(c) if c.card_type.value == "daily" else None,
                "daily_start": str(c.daily_start) if c.daily_start else None,
            }
            for c in active
        ]
    )


@router.get("/user/coupons", response_model=ResponseModel)
def get_coupons(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from app.models import Coupon

    coupons = db.scalars(select(Coupon).where(Coupon.user_id == user.id).order_by(Coupon.id.desc())).all()
    return ResponseModel(
        data=[
            {
                "id": c.id,
                "coupon_name": c.coupon_name,
                "discount_type": c.discount_type,
                "discount_val": float(c.discount_val or 0),
                "min_amount": float(c.min_amount or 0),
                "expire_date": str(c.expire_date) if c.expire_date else None,
                "status": c.status,
            }
            for c in coupons
        ]
    )
