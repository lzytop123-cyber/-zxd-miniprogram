"""收款管理：只登记收款与已完成退款，不发起支付操作。"""
from datetime import date
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin
from app.db.session import get_db
from app.models import AdminUser
from app.models.receipts import Receipt, ReceiptRefund
from app.schemas.common import PageResult, ResponseModel
from app.services.admin_audit import log_admin_action
from app.services import receipts as svc

router = APIRouter(prefix="/admin/receipts", tags=["后台-收款管理"])
Amount = Annotated[Decimal, Field(gt=0, lt=100000000, decimal_places=2, max_digits=10)]
Channel = Literal["meituan", "douyin", "wechat_pay", "wechat_transfer"]


class ReceiptBody(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    channel: Literal["meituan", "douyin", "wechat_transfer"]
    amount: Amount
    received_on: date
    customer: str = Field(default="", max_length=100)
    reference: str = Field(default="", max_length=100)
    remark: str = Field(default="", max_length=500)
    request_id: UUID

    @field_validator("received_on")
    @classmethod
    def past_date(cls, value):
        if value > svc.today():
            raise ValueError("收款日期不能晚于今天")
        return value


class DateBody(BaseModel):
    received_on: date


class RefundBody(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    amount: Amount
    refunded_on: date
    reason: str = Field(min_length=1, max_length=500)
    completed: Literal[True]
    request_id: UUID


def get_receipt(db, receipt_id):
    row = db.get(Receipt, receipt_id)
    if not row:
        raise HTTPException(404, "收款记录不存在")
    return row


def receipt_retry(row: Receipt, body: ReceiptBody):
    if any((getattr(row, key) or "") != (value or "") for key, value in body.model_dump(exclude={"request_id"}).items()):
        raise HTTPException(409, "该请求已保存其他内容，请刷新后重新登记")
    return ResponseModel(data=svc.receipt_item(row))


def refund_retry(row: ReceiptRefund, receipt: Receipt, body: RefundBody):
    if row.receipt_id != receipt.id or row.amount != body.amount or row.refunded_on != body.refunded_on or row.reason != body.reason:
        raise HTTPException(409, "该请求已保存其他退款内容，请刷新后重新登记")
    return ResponseModel(data=svc.refund_item(row, receipt))


@router.get("/summary", response_model=ResponseModel)
def summary(
    year: int = Query(..., ge=2000, le=9998), month: int | None = Query(None, ge=1, le=12),
    channel: Channel | None = None, _: AdminUser = Depends(get_current_admin), db: Session = Depends(get_db),
):
    start, end = svc.period(year, month)
    return ResponseModel(data={
        "month": svc.totals(db, start, end, channel),
        "year": svc.totals(db, *svc.period(year), channel),
        "channels": [{"channel": key, **svc.totals(db, start, end, key)} for key in svc.CHANNELS if not channel or key == channel],
        "missing_dates": db.scalar(select(func.count()).select_from(Receipt).where(Receipt.received_on.is_(None))) or 0,
        "refunds_to_review": db.scalar(select(func.count()).select_from(Receipt).where(Receipt.source_refunded == True, Receipt.refunded_amount < Receipt.amount)) or 0,
    })


@router.post("/sync-wechat", response_model=ResponseModel)
def sync(admin: AdminUser = Depends(get_current_admin), db: Session = Depends(get_db)):
    added = svc.sync_wechat(db)
    if added:
        log_admin_action(db, admin, "receipt_sync", target_type="receipt", detail=f"同步 {added} 笔微信支付")
    db.commit()
    return ResponseModel(data={"added": added})


def filtered(query, date_col, year, month, channel, keyword):
    if month and not year:
        raise HTTPException(422, "按月筛选必须指定年份")
    if year:
        start, end = svc.period(year, month)
        query = query.where(date_col >= start, date_col < end)
    if channel:
        query = query.where(Receipt.channel == channel)
    if keyword:
        value = f"%{keyword.strip()}%"
        query = query.where(or_(Receipt.customer.like(value), Receipt.reference.like(value), Receipt.remark.like(value)))
    return query


@router.get("", response_model=ResponseModel)
def listing(
    year: int | None = Query(None, ge=2000, le=9998), month: int | None = Query(None, ge=1, le=12),
    channel: Channel | None = None, keyword: str | None = Query(None, max_length=100),
    needs_date: bool = False, needs_refund: bool = False,
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    _: AdminUser = Depends(get_current_admin), db: Session = Depends(get_db),
):
    query = filtered(select(Receipt), Receipt.received_on, None if needs_date else year, None if needs_date else month, channel, keyword)
    if needs_date:
        query = query.where(Receipt.received_on.is_(None))
    if needs_refund:
        query = query.where(Receipt.source_refunded == True, Receipt.refunded_amount < Receipt.amount)
    count = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.scalars(query.order_by(Receipt.received_on.desc(), Receipt.id.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return ResponseModel(data=PageResult(items=[svc.receipt_item(row) for row in rows], total=count, page=page, page_size=page_size))


@router.get("/refunds", response_model=ResponseModel)
def refunds(
    year: int | None = Query(None, ge=2000, le=9998), month: int | None = Query(None, ge=1, le=12),
    channel: Channel | None = None, keyword: str | None = Query(None, max_length=100),
    receipt_id: int | None = None, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    _: AdminUser = Depends(get_current_admin), db: Session = Depends(get_db),
):
    query = filtered(select(ReceiptRefund, Receipt).join(Receipt), ReceiptRefund.refunded_on, year, month, channel, keyword)
    if receipt_id:
        query = query.where(ReceiptRefund.receipt_id == receipt_id)
    count = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.execute(query.order_by(ReceiptRefund.refunded_on.desc(), ReceiptRefund.id.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return ResponseModel(data=PageResult(items=[svc.refund_item(*row) for row in rows], total=count, page=page, page_size=page_size))


@router.post("", response_model=ResponseModel)
def create(body: ReceiptBody, admin: AdminUser = Depends(get_current_admin), db: Session = Depends(get_db)):
    source_key = "manual:" + str(body.request_id)
    existing = db.scalar(select(Receipt).where(Receipt.source_key == source_key))
    if existing:
        return receipt_retry(existing, body)
    row = Receipt(source_key=source_key, **body.model_dump(exclude={"request_id"}))
    row.reference = row.reference or None
    try:
        db.add(row)
        db.flush()
        log_admin_action(db, admin, "receipt_create", target_type="receipt", target_id=row.id, detail=body.model_dump_json())
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(select(Receipt).where(Receipt.source_key == source_key))
        if existing:
            return receipt_retry(existing, body)
        raise HTTPException(409, "该渠道的流水号已经登记，请检查重复收款")
    return ResponseModel(data=svc.receipt_item(row))


@router.patch("/{receipt_id}/date", response_model=ResponseModel)
def confirm_date(receipt_id: int, body: DateBody, admin: AdminUser = Depends(get_current_admin), db: Session = Depends(get_db)):
    get_receipt(db, receipt_id)
    if body.received_on > svc.today():
        raise HTTPException(400, "收款日期不能晚于今天")
    changed = db.execute(update(Receipt).where(Receipt.id == receipt_id, Receipt.received_on.is_(None)).values(received_on=body.received_on))
    if changed.rowcount != 1:
        raise HTTPException(409, "该笔收款已有日期，请刷新列表")
    log_admin_action(db, admin, "receipt_date", target_type="receipt", target_id=receipt_id, detail=body.received_on.isoformat())
    db.commit()
    return ResponseModel(data=svc.receipt_item(get_receipt(db, receipt_id)))


@router.post("/{receipt_id}/refunds", response_model=ResponseModel)
def create_refund(receipt_id: int, body: RefundBody, admin: AdminUser = Depends(get_current_admin), db: Session = Depends(get_db)):
    receipt = get_receipt(db, receipt_id)
    request_id = str(body.request_id)
    existing = db.scalar(select(ReceiptRefund).where(ReceiptRefund.request_id == request_id))
    if existing:
        return refund_retry(existing, receipt, body)
    if not receipt.received_on:
        raise HTTPException(400, "请先补全实际收款日期")
    if not receipt.received_on <= body.refunded_on <= svc.today():
        raise HTTPException(400, "退款日期须在收款日期至今天之间")
    try:
        row = ReceiptRefund(receipt_id=receipt_id, request_id=request_id, amount=body.amount, refunded_on=body.refunded_on, reason=body.reason)
        # Insert the request key first: a simultaneous retry must not increment twice.
        db.add(row)
        db.flush()
        changed = db.execute(update(Receipt).where(Receipt.id == receipt_id, Receipt.refunded_amount + body.amount <= Receipt.amount).values(refunded_amount=Receipt.refunded_amount + body.amount))
        if changed.rowcount != 1:
            db.rollback()
            raise HTTPException(400, "累计退款不能超过原收款金额")
        log_admin_action(db, admin, "receipt_refund", target_type="receipt", target_id=receipt_id, detail=body.model_dump_json())
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(select(ReceiptRefund).where(ReceiptRefund.request_id == request_id))
        if existing and existing.receipt_id == receipt_id:
            return refund_retry(existing, receipt, body)
        raise HTTPException(409, "退款记录冲突，请刷新后重试")
    return ResponseModel(data=svc.refund_item(row, receipt))
