from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Coupon, PayType, Reservation
from app.services.business import create_ble_keys_for_reservation
from app.services.coupon_service import mark_coupon_used
from app.services.wechat_pay import WechatPayService

router = APIRouter(prefix="/payment", tags=["支付"])


def _apply_coupon_from_attach(db: Session, reservation: Reservation, attach: str | None) -> None:
    if not attach or not attach.startswith("coupon_id="):
        return
    try:
        coupon_id = int(attach.split("=", 1)[1])
    except ValueError:
        return
    coupon = db.get(Coupon, coupon_id)
    if coupon and coupon.user_id == reservation.user_id and coupon.status == 0:
        mark_coupon_used(db, coupon, reservation)


@router.post("/wechat/notify")
async def wechat_pay_notify(request: Request, db: Session = Depends(get_db)):
    """微信支付结果回调（生产环境需配置商户平台 notify_url）。"""
    body = await request.body()
    result = WechatPayService.verify_notify(dict(request.headers), body)
    if not result:
        raise HTTPException(status_code=400, detail="invalid notify")

    order_no = result.get("out_trade_no")
    if order_no and result.get("trade_state") == "SUCCESS":
        reservation = db.scalar(select(Reservation).where(Reservation.order_no == order_no))
        if reservation and reservation.pay_status != 1:
            reservation.pay_status = 1
            reservation.pay_type = PayType.wechat
            _apply_coupon_from_attach(db, reservation, result.get("attach"))
            db.commit()
            await create_ble_keys_for_reservation(db, reservation)
    return {"code": "SUCCESS", "message": "成功"}
