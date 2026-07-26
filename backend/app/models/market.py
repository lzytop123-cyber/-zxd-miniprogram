"""上岸集市：学员闲置资料信息发布（不含平台支付/官方销售）。"""

from __future__ import annotations

import enum
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class MarketCategoryType(str, enum.Enum):
    exam = "exam"
    material = "material"


class MarketListingStatus(str, enum.Enum):
    draft = "draft"
    pending = "pending"
    published = "published"
    rejected = "rejected"
    off = "off"
    sold = "sold"
    violation = "violation"


class MarketContactStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    cancelled = "cancelled"
    expired = "expired"


class MarketReportStatus(str, enum.Enum):
    pending = "pending"
    accepted = "accepted"
    rejected = "rejected"


class MarketRevealType(str, enum.Enum):
    wechat = "wechat"
    phone = "phone"


class MarketCategory(Base):
    __tablename__ = "market_categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (UniqueConstraint("type", "code", name="uq_market_category_type_code"),)


class MarketListing(Base):
    __tablename__ = "market_listings"
    __table_args__ = (
        Index("ix_market_listings_status_published", "status", "published_at"),
        Index("ix_market_listings_store_status", "store_id", "status"),
        Index("ix_market_listings_user", "user_id"),
        Index("ix_market_listings_categories", "exam_category_id", "material_category_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    store_id: Mapped[int] = mapped_column(Integer, ForeignKey("stores.id"), nullable=False)
    exam_category_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("market_categories.id"), nullable=False
    )
    material_category_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("market_categories.id"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"))
    is_free: Mapped[int] = mapped_column(Integer, default=0)
    images: Mapped[list | None] = mapped_column(JSON, default=list)
    copyright_declared: Mapped[int] = mapped_column(Integer, default=0)
    copyright_text_version: Mapped[str | None] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default=MarketListingStatus.draft.value)
    reject_reason: Mapped[str | None] = mapped_column(String(200))
    view_count: Mapped[int] = mapped_column(Integer, default=0)
    favorite_count: Mapped[int] = mapped_column(Integer, default=0)
    contact_count: Mapped[int] = mapped_column(Integer, default=0)
    published_at: Mapped[datetime | None] = mapped_column(DateTime)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)
    reviewed_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("admin_users.id"))
    content_safe_text_ok: Mapped[int | None] = mapped_column(Integer)
    content_safe_image_ok: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class MarketFavorite(Base):
    __tablename__ = "market_favorites"
    __table_args__ = (UniqueConstraint("user_id", "listing_id", name="uq_market_favorite"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    listing_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("market_listings.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class MarketContactRequest(Base):
    __tablename__ = "market_contact_requests"
    __table_args__ = (
        Index("ix_market_contact_buyer", "buyer_id", "created_at"),
        Index("ix_market_contact_seller", "seller_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    listing_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("market_listings.id"), nullable=False
    )
    buyer_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    seller_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    message: Mapped[str | None] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(20), default=MarketContactStatus.pending.value)
    reveal_type: Mapped[str | None] = mapped_column(String(20))
    reveal_value: Mapped[str | None] = mapped_column(String(100))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime)
    expired_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class MarketReport(Base):
    __tablename__ = "market_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    listing_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("market_listings.id"), nullable=False
    )
    reporter_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    reason_code: Mapped[str] = mapped_column(String(40), nullable=False)
    detail: Mapped[str | None] = mapped_column(String(500))
    images: Mapped[list | None] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(20), default=MarketReportStatus.pending.value)
    handler_admin_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("admin_users.id"))
    handle_note: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    handled_at: Mapped[datetime | None] = mapped_column(DateTime)


class MarketSensitiveWord(Base):
    __tablename__ = "market_sensitive_words"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    word: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    level: Mapped[str] = mapped_column(String(20), default="block")  # block | review
    status: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class MarketModerationLog(Base):
    __tablename__ = "market_moderation_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    target_type: Mapped[str] = mapped_column(String(30), nullable=False)
    target_id: Mapped[str] = mapped_column(String(50), nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    admin_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("admin_users.id"))
    user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"))
    detail: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
