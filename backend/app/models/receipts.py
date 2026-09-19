"""经营收款台账；不控制实际支付或用户资产。"""
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Receipt(Base):
    __tablename__ = "receipts"
    __table_args__ = (
        UniqueConstraint("channel", "reference", name="uq_receipt_channel_reference"),
        CheckConstraint("amount > 0 AND refunded_amount >= 0 AND refunded_amount <= amount", name="ck_receipt_amount"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_key: Mapped[str] = mapped_column(String(100), unique=True)
    channel: Mapped[str] = mapped_column(String(30), index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    refunded_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0"))
    received_on: Mapped[date | None] = mapped_column(Date, index=True)
    customer: Mapped[str | None] = mapped_column(String(100))
    reference: Mapped[str | None] = mapped_column(String(100))
    remark: Mapped[str | None] = mapped_column(String(500))
    source_refunded: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class ReceiptRefund(Base):
    __tablename__ = "receipt_refunds"
    __table_args__ = (CheckConstraint("amount > 0", name="ck_receipt_refund_amount"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    request_id: Mapped[str] = mapped_column(String(36), unique=True)
    receipt_id: Mapped[int] = mapped_column(ForeignKey("receipts.id"), index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    refunded_on: Mapped[date] = mapped_column(Date, index=True)
    reason: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
