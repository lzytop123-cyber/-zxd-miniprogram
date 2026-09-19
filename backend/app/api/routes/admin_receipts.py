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
from app.models import AdminUser, MeituanOrder
from app.models.receipts import Receipt, ReceiptRefund
from app.schemas.common import PageResult, ResponseModel
from app.services.admin_audit import log_admin_action
from app.services import receipts as svc
from app.services import platform_receipts as platform_svc

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


class PlatformConfirmBody(BaseModel):
    channel: Literal["meituan", "douyin"]
    amount: Amount
    received_on: date
    confirmed: Literal[True]
    existing_receipt_id: int | None = Field(None, gt=0)


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
        "platforms_to_review": len(platform_svc.candidates(db)),
    })


@router.post("/sync-wechat", response_model=ResponseModel)
def sync(admin: AdminUser = Depends(get_current_admin), db: Session = Depends(get_db)):
    added = svc.sync_wechat(db)
    if added:
        log_admin_action(db, admin, "receipt_sync", target_type="receipt", detail=f"同步 {added} 笔微信支付")
    db.commit()
    return ResponseModel(data={"added": added})


@router.post("/sync", response_model=ResponseModel)
def sync_all(admin: AdminUser = Depends(get_current_admin), db: Session = Depends(get_db)):
    wechat = svc.sync_wechat(db)
    platforms = platform_svc.sync_platforms(db)
    if wechat or platforms:
        log_admin_action(db, admin, "receipt_sync", target_type="receipt", detail=f"微信支付 {wechat} 笔，平台核销 {platforms} 笔")
    db.commit()
    return ResponseModel(data={"added": wechat + platforms, "wechat": wechat, "platforms": platforms})


@router.get("/platform-review", response_model=ResponseModel)
def platform_review(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), _: AdminUser = Depends(get_current_admin), db: Session = Depends(get_db)):
    items = platform_svc.candidates(db)
    return ResponseModel(data=PageResult(items=items[(page - 1) * page_size:page * page_size], total=len(items), page=page, page_size=page_size))


@router.post("/platform-review/bulk-reconcile", response_model=ResponseModel)
def bulk_reconcile(admin: AdminUser = Depends(get_current_admin), db: Session = Depends(get_db)):
    """先关联已有手工登记，再用参考价把剩余能定的批量入账；其余保持待核对。"""
    linked = inserted = skipped = 0
    for item in platform_svc.candidates(db):
        channel, day = item["channel"], item["received_on"]
        amount = item["amount"] or item["reference_price"]
        if not channel or not day or not amount or day > svc.today():
            skipped += 1
            continue
        amount = Decimal(amount)
        key = platform_svc.source_key(item["id"])
        if db.scalar(select(Receipt.id).where(Receipt.source_key == key)):
            skipped += 1
            continue
        if item["existing_receipt_id"]:
            row = db.get(Receipt, item["existing_receipt_id"])
            if not row or not row.source_key.startswith("manual:") or row.channel != channel or row.amount != amount or row.received_on != day:
                skipped += 1
                continue
            changed = db.execute(update(Receipt).where(Receipt.id == row.id, Receipt.source_key == row.source_key).values(source_key=key, source_refunded=item["source_refunded"]))
            if changed.rowcount != 1:
                skipped += 1
                continue
            linked += 1
        else:
            row = Receipt(source_key=key, channel=channel, amount=amount, received_on=day,
                          reference=item["reference"], customer=item["customer"],
                          remark=f"核销收款（一键核对） · {item['deal_name']}"[:500], source_refunded=item["source_refunded"])
            try:
                with db.begin_nested():
                    db.add(row)
                    db.flush()
                inserted += 1
            except IntegrityError:
                skipped += 1
    if linked or inserted:
        log_admin_action(db, admin, "receipt_platform_bulk", target_type="receipt",
                         detail=f"一键核对：关联 {linked} 笔，入账 {inserted} 笔，跳过 {skipped} 笔")
    db.commit()
    return ResponseModel(data={"linked": linked, "inserted": inserted, "skipped": skipped})


@router.post("/platform-review/{order_id}/confirm", response_model=ResponseModel)
def confirm_platform(order_id: int, body: PlatformConfirmBody, admin: AdminUser = Depends(get_current_admin), db: Session = Depends(get_db)):
    order = db.get(MeituanOrder, order_id)
    if not order or order.status not in platform_svc.ELIGIBLE:
        raise HTTPException(404, "未找到已核销记录")
    if body.received_on > svc.today():
        raise HTTPException(400, "核销入账日期不能晚于今天")
    key = platform_svc.source_key(order_id)

    def existing_response(row):
        if row.channel != body.channel or row.amount != body.amount or row.received_on != body.received_on or (body.existing_receipt_id and row.id != body.existing_receipt_id):
            raise HTTPException(409, "该核销记录已入账，请刷新后核对")
        return ResponseModel(data=svc.receipt_item(row))

    existing = db.scalar(select(Receipt).where(Receipt.source_key == key))
    if existing:
        return existing_response(existing)
    item = next((item for item in platform_svc.candidates(db) if item["id"] == order_id), None)
    if item is None:
        raise HTTPException(409, "记录已更新，请刷新后核对")
    if item["channel"] and item["channel"] != body.channel:
        raise HTTPException(400, "渠道与核销记录不一致")
    try:
        if body.existing_receipt_id:
            if item["existing_receipt_id"] and item["existing_receipt_id"] != body.existing_receipt_id:
                raise HTTPException(409, "请关联该流水号对应的原收款记录")
            row = get_receipt(db, body.existing_receipt_id)
            if not row.source_key.startswith("manual:") or row.channel != body.channel or row.amount != body.amount or row.received_on != body.received_on:
                raise HTTPException(409, "只能关联渠道、金额、日期一致的手工收款记录")
            changed = db.execute(update(Receipt).where(Receipt.id == row.id, Receipt.source_key == row.source_key).values(source_key=key, source_refunded=item["source_refunded"]))
            if changed.rowcount != 1:
                raise HTTPException(409, "原收款已被关联，请刷新")
        else:
            if item["existing_receipt_id"]:
                raise HTTPException(409, "该流水号已手工登记，请关联原收款，避免重复入账")
            row = Receipt(source_key=key, channel=body.channel, amount=body.amount, received_on=body.received_on,
                          reference=item["reference"], customer=item["customer"],
                          remark=f"核销收款（人工核对） · {item['deal_name']}"[:500], source_refunded=item["source_refunded"])
            db.add(row)
            db.flush()
        log_admin_action(db, admin, "receipt_platform_confirm", target_type="receipt", target_id=row.id, detail=f"核销 #{order_id}: {body.model_dump_json()}")
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(select(Receipt).where(Receipt.source_key == key))
        if existing:
            return existing_response(existing)
        raise HTTPException(409, "已有相同流水号，请关联原记录或刷新后重试")
    return ResponseModel(data=svc.receipt_item(row))


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
