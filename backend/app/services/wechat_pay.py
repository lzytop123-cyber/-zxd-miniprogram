import hashlib
import json
import logging
import secrets
import time
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

from wechatpayv3 import WeChatPay, WeChatPayType

from app.core.config import settings

logger = logging.getLogger(__name__)


def _is_mock_mode() -> bool:
    return settings.app_env == "development" or not settings.wx_pay_mchid


def _amount_fen(amount: Decimal) -> int:
    return int((amount * 100).quantize(Decimal("1")))


@lru_cache(maxsize=1)
def _get_client() -> WeChatPay:
    key_path = Path(settings.wx_pay_key_path)
    if not key_path.is_file():
        raise RuntimeError(f"微信支付私钥不存在: {key_path}")

    cert_dir = str(key_path.parent)
    notify_url = f"{settings.base_url.rstrip('/')}/api/payment/wechat/notify"

    return WeChatPay(
        wechatpay_type=WeChatPayType.MINIPROG,
        mchid=settings.wx_pay_mchid,
        private_key=key_path.read_text(encoding="utf-8"),
        cert_serial_no=settings.wx_pay_serial_no,
        apiv3_key=settings.wx_pay_api_v3_key,
        appid=settings.wx_appid,
        notify_url=notify_url,
        cert_dir=cert_dir,
        logger=logger,
        partner_mode=False,
    )


class WechatPayService:
    """微信支付 v3 封装（开发环境返回模拟参数）"""

    @staticmethod
    def create_jsapi_order(
        order_no: str,
        amount: Decimal,
        openid: str,
        description: str,
        attach: str | None = None,
    ) -> dict:
        if _is_mock_mode():
            nonce = secrets.token_hex(16)
            timestamp = str(int(time.time()))
            return {
                "timeStamp": timestamp,
                "nonceStr": nonce,
                "package": f"prepay_id=mock_prepay_{order_no}",
                "signType": "RSA",
                "paySign": hashlib.sha256(f"{order_no}{nonce}".encode()).hexdigest(),
            }

        wxpay = _get_client()
        code, message = wxpay.pay(
            description=description,
            out_trade_no=order_no,
            amount={"total": _amount_fen(amount), "currency": "CNY"},
            payer={"openid": openid},
            attach=attach,
            pay_type=WeChatPayType.MINIPROG,
        )
        if code != 200:
            logger.error("wechat pay failed: code=%s message=%s", code, message)
            raise RuntimeError(f"微信支付下单失败: {message}")

        prepay_id = json.loads(message)["prepay_id"]
        timestamp = str(int(time.time()))
        nonce_str = secrets.token_hex(16)
        package = f"prepay_id={prepay_id}"
        pay_sign = wxpay.sign([settings.wx_appid, timestamp, nonce_str, package])
        return {
            "timeStamp": timestamp,
            "nonceStr": nonce_str,
            "package": package,
            "signType": "RSA",
            "paySign": pay_sign,
        }

    @staticmethod
    def verify_notify(headers: dict, body: bytes) -> dict | None:
        if _is_mock_mode():
            return {"out_trade_no": "", "trade_state": "SUCCESS"}

        wxpay = _get_client()
        result = wxpay.callback(headers, body)
        if not result:
            return None

        resource = result.get("resource") or {}
        trade_state = resource.get("trade_state")
        if trade_state != "SUCCESS" and result.get("event_type") != "TRANSACTION.SUCCESS":
            return None

        return {
            "out_trade_no": resource.get("out_trade_no"),
            "trade_state": trade_state or "SUCCESS",
            "attach": resource.get("attach"),
        }

    @staticmethod
    def refund(order_no: str, refund_amount: Decimal, total_amount: Decimal, reason: str) -> bool:
        if _is_mock_mode():
            return True

        wxpay = _get_client()
        out_refund_no = f"RF{order_no}{int(time.time()) % 100000:05d}"
        code, message = wxpay.refund(
            out_refund_no=out_refund_no,
            out_trade_no=order_no,
            reason=reason,
            amount={
                "refund": _amount_fen(refund_amount),
                "total": _amount_fen(total_amount),
                "currency": "CNY",
            },
        )
        if code != 200:
            logger.error("wechat refund failed: code=%s message=%s", code, message)
            return False
        return True
