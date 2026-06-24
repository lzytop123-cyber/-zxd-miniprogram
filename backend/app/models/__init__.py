import enum
from datetime import date, datetime, time
from decimal import Decimal

from sqlalchemy import (
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    Time,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class BillType(str, enum.Enum):
    hourly = "hourly"
    daily = "daily"
    weekly = "weekly"
    monthly = "monthly"
    quarterly = "quarterly"
    night = "night"
    night_monthly = "night_monthly"
    session = "session"
    custom = "custom"


class PayType(str, enum.Enum):
    balance = "balance"
    wechat = "wechat"
    period_card = "period_card"


class CardType(str, enum.Enum):
    hourly = "hourly"
    daily = "daily"
    weekly = "weekly"
    monthly = "monthly"
    quarterly = "quarterly"
    night_monthly = "night_monthly"
    session = "session"
    custom = "custom"


class CardSource(str, enum.Enum):
    purchase = "purchase"
    meituan = "meituan"
    douyin = "douyin"
    admin = "admin"
    gift = "gift"


class LockType(str, enum.Enum):
    door = "door"
    cabinet = "cabinet"


class KeyType(str, enum.Enum):
    permanent = "permanent"
    timed = "timed"
    one_time = "one_time"


class OpenType(str, enum.Enum):
    ble = "ble"
    admin = "admin"
    auto = "auto"
    remote = "remote"


class MeituanOrderStatus(str, enum.Enum):
    pending = "pending"
    verified = "verified"
    refunded = "refunded"


class RewardType(str, enum.Enum):
    hours = "hours"
    day_pass = "day_pass"
    week_pass = "week_pass"
    month_pass = "month_pass"
    quarter_pass = "quarter_pass"
    night_monthly = "night_monthly"
    session = "session"
    custom = "custom"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    openid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    nickname: Mapped[str | None] = mapped_column(String(50))
    avatar_url: Mapped[str | None] = mapped_column(String(500))
    phone: Mapped[str | None] = mapped_column(String(20))
    real_name: Mapped[str | None] = mapped_column(String(50))
    face_image: Mapped[str | None] = mapped_column(String(500))
    title: Mapped[str | None] = mapped_column(String(20), default="小白")
    balance: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"))
    total_points: Mapped[int] = mapped_column(Integer, default=0)
    invite_code: Mapped[str | None] = mapped_column(String(20), unique=True)
    invited_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class AdminUser(Base):
    __tablename__ = "admin_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(200), nullable=False)
    name: Mapped[str | None] = mapped_column(String(50))
    status: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Store(Base):
    __tablename__ = "stores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    address: Mapped[str | None] = mapped_column(String(500))
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(10, 7))
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(10, 7))
    open_time: Mapped[time | None] = mapped_column(Time)
    close_time: Mapped[time | None] = mapped_column(Time)
    cover_images: Mapped[list | None] = mapped_column(JSON)
    floor_plan: Mapped[str | None] = mapped_column(String(500))
    wifi_name: Mapped[str | None] = mapped_column(String(100))
    wifi_password: Mapped[str | None] = mapped_column(String(100))
    meituan_shop_id: Mapped[str | None] = mapped_column(String(100))
    meituan_auth_token: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    zones: Mapped[list["Zone"]] = relationship(back_populates="store")
    seats: Mapped[list["Seat"]] = relationship(back_populates="store")


class Zone(Base):
    __tablename__ = "zones"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    store_id: Mapped[int] = mapped_column(Integer, ForeignKey("stores.id"), nullable=False)
    name: Mapped[str | None] = mapped_column(String(50))
    type: Mapped[str | None] = mapped_column(String(20))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    store: Mapped["Store"] = relationship(back_populates="zones")
    seats: Mapped[list["Seat"]] = relationship(back_populates="zone")


class Seat(Base):
    __tablename__ = "seats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    store_id: Mapped[int] = mapped_column(Integer, ForeignKey("stores.id"), nullable=False)
    zone_id: Mapped[int] = mapped_column(Integer, ForeignKey("zones.id"), nullable=False)
    seat_code: Mapped[str] = mapped_column(String(20), nullable=False)
    seat_type: Mapped[str | None] = mapped_column(String(20), default="standard")
    has_outlet: Mapped[int] = mapped_column(Integer, default=1)
    has_curtain: Mapped[int] = mapped_column(Integer, default=0)
    qr_code: Mapped[str | None] = mapped_column(String(500))
    pos_x: Mapped[int | None] = mapped_column(Integer)
    pos_y: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[int] = mapped_column(Integer, default=1)
    is_buffer: Mapped[int] = mapped_column(Integer, default=0)

    store: Mapped["Store"] = relationship(back_populates="seats")
    zone: Mapped["Zone"] = relationship(back_populates="seats")


class PricingRule(Base):
    __tablename__ = "pricing_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    store_id: Mapped[int] = mapped_column(Integer, ForeignKey("stores.id"), nullable=False)
    bill_type: Mapped[BillType] = mapped_column(Enum(BillType), nullable=False)
    seat_type: Mapped[str] = mapped_column(String(20), default="standard")
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    min_hours: Mapped[int | None] = mapped_column(Integer)
    max_hours: Mapped[int | None] = mapped_column(Integer)
    night_start: Mapped[time | None] = mapped_column(Time)
    night_end: Mapped[time | None] = mapped_column(Time)
    valid_days: Mapped[int | None] = mapped_column(Integer)
    daily_limit: Mapped[time | None] = mapped_column(Time)
    remark: Mapped[str | None] = mapped_column(String(200))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[int] = mapped_column(Integer, default=1)


class Reservation(Base):
    __tablename__ = "reservations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_no: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    store_id: Mapped[int] = mapped_column(Integer, ForeignKey("stores.id"), nullable=False)
    seat_id: Mapped[int] = mapped_column(Integer, ForeignKey("seats.id"), nullable=False)
    bill_type: Mapped[BillType] = mapped_column(Enum(BillType), nullable=False)
    start_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    actual_end_time: Mapped[datetime | None] = mapped_column(DateTime)
    duration_hours: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    original_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    discount_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"))
    final_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    pay_type: Mapped[PayType | None] = mapped_column(Enum(PayType))
    pay_status: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[int] = mapped_column(Integer, default=0)
    check_in_time: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class PeriodCard(Base):
    __tablename__ = "period_cards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    store_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("stores.id"))
    card_name: Mapped[str | None] = mapped_column(String(100))
    card_type: Mapped[CardType] = mapped_column(Enum(CardType), nullable=False)
    total_sessions: Mapped[int | None] = mapped_column(Integer)
    remaining_sessions: Mapped[int | None] = mapped_column(Integer)
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    remaining_hours: Mapped[Decimal | None] = mapped_column(Numeric(5, 1))
    daily_start: Mapped[time | None] = mapped_column(Time)
    daily_end: Mapped[time | None] = mapped_column(Time)
    source: Mapped[CardSource] = mapped_column(Enum(CardSource), default=CardSource.purchase)
    meituan_receipt: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[int] = mapped_column(Integer, default=1)
    remark: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Coupon(Base):
    __tablename__ = "coupons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    coupon_name: Mapped[str | None] = mapped_column(String(100))
    discount_type: Mapped[str | None] = mapped_column(String(20))
    discount_val: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    min_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"))
    expire_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[int] = mapped_column(Integer, default=0)


class WalletLog(Base):
    __tablename__ = "wallet_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    balance_after: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    remark: Mapped[str | None] = mapped_column(String(200))
    ref_order: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class PointLog(Base):
    __tablename__ = "point_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    points: Mapped[int] = mapped_column(Integer, nullable=False)
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    remark: Mapped[str | None] = mapped_column(String(200))
    ref_order: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class BleBatteryAlert(Base):
    __tablename__ = "ble_battery_alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lock_id: Mapped[int] = mapped_column(Integer, ForeignKey("ble_locks.id"), nullable=False)
    battery_level: Mapped[int] = mapped_column(Integer, nullable=False)
    message: Mapped[str | None] = mapped_column(String(200))
    is_read: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class StudyStat(Base):
    __tablename__ = "study_stats"
    __table_args__ = (UniqueConstraint("user_id", "store_id", "stat_date", name="uk_user_store_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    store_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("stores.id"))
    stat_date: Mapped[date] = mapped_column(Date, nullable=False)
    total_minutes: Mapped[int] = mapped_column(Integer, default=0)
    session_count: Mapped[int] = mapped_column(Integer, default=0)


class BleLock(Base):
    __tablename__ = "ble_locks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    store_id: Mapped[int] = mapped_column(Integer, ForeignKey("stores.id"), nullable=False)
    lock_name: Mapped[str | None] = mapped_column(String(100))
    lock_type: Mapped[LockType] = mapped_column(Enum(LockType), default=LockType.door)
    brand: Mapped[str | None] = mapped_column(String(50), default="ttlock")
    lock_id: Mapped[str | None] = mapped_column(String(100))
    mac_address: Mapped[str | None] = mapped_column(String(20))
    lock_data: Mapped[str | None] = mapped_column(Text)
    battery_level: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class BleKey(Base):
    __tablename__ = "ble_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lock_id: Mapped[int] = mapped_column(Integer, ForeignKey("ble_locks.id"), nullable=False)
    reservation_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("reservations.id"))
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    key_type: Mapped[KeyType] = mapped_column(Enum(KeyType), default=KeyType.timed)
    ttlock_key_id: Mapped[str | None] = mapped_column(String(100))
    lock_data: Mapped[str | None] = mapped_column(Text)
    start_time: Mapped[datetime | None] = mapped_column(DateTime)
    end_time: Mapped[datetime | None] = mapped_column(DateTime)
    used_at: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class DoorLog(Base):
    __tablename__ = "door_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lock_id: Mapped[int] = mapped_column(Integer, ForeignKey("ble_locks.id"), nullable=False)
    user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"))
    reservation_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("reservations.id"))
    open_type: Mapped[OpenType] = mapped_column(Enum(OpenType), default=OpenType.ble)
    result: Mapped[int] = mapped_column(Integer, default=1)
    fail_reason: Mapped[str | None] = mapped_column(String(200))
    opened_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class MeituanOrder(Base):
    __tablename__ = "meituan_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    meituan_deal_id: Mapped[str | None] = mapped_column(String(100))
    meituan_order_id: Mapped[str | None] = mapped_column(String(100), unique=True)
    user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"))
    coupon_code: Mapped[str | None] = mapped_column(String(100))
    deal_name: Mapped[str | None] = mapped_column(String(200))
    deal_type: Mapped[str | None] = mapped_column(String(50))
    hours_value: Mapped[int | None] = mapped_column(Integer)
    session_value: Mapped[int | None] = mapped_column(Integer)
    store_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("stores.id"))
    verify_code: Mapped[str | None] = mapped_column(String(50))
    status: Mapped[MeituanOrderStatus] = mapped_column(
        Enum(MeituanOrderStatus), default=MeituanOrderStatus.pending
    )
    verified_at: Mapped[datetime | None] = mapped_column(DateTime)
    meituan_raw: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class MeituanDealMapping(Base):
    __tablename__ = "meituan_deal_mapping"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    store_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("stores.id"))
    deal_id: Mapped[str] = mapped_column(String(100), nullable=False)
    deal_name: Mapped[str | None] = mapped_column(String(200))
    reward_type: Mapped[RewardType] = mapped_column(Enum(RewardType), nullable=False)
    reward_value: Mapped[int | None] = mapped_column(Integer)
    night_start: Mapped[time | None] = mapped_column(Time)
    night_end: Mapped[time | None] = mapped_column(Time)
    is_active: Mapped[int] = mapped_column(Integer, default=1)


class PendingDealMapping(Base):
    __tablename__ = "pending_deal_mapping"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    deal_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    deal_name: Mapped[str | None] = mapped_column(String(200))
    platform: Mapped[int] = mapped_column(Integer, default=1)
    last_coupon_code: Mapped[str | None] = mapped_column(String(50))
    ticket_snapshot: Mapped[dict | None] = mapped_column(JSON)
    suggested_reward_type: Mapped[RewardType | None] = mapped_column(Enum(RewardType))
    suggested_reward_value: Mapped[int | None] = mapped_column(Integer)
    hit_count: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class WechatSubscription(Base):
    __tablename__ = "wechat_subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    tmpl_id: Mapped[str | None] = mapped_column(String(100))
    scene: Mapped[str | None] = mapped_column(String(50))
    status: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
