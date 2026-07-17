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


# backend/ 根目录（不依赖 systemd 的 WorkingDirectory）
_BACKEND_ROOT = Path(__file__).resolve().parents[2]


def _resolve_path(path_str: str) -> Path:
    path = Path((path_str or "").strip())
    if not path:
        return path
    if path.is_absolute():
        return path
    candidates = [
        Path.cwd() / path,
        _BACKEND_ROOT / path,
        _BACKEND_ROOT / path.name,
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return _BACKEND_ROOT / path


def _find_public_key_file(explicit_path: str) -> Path | None:
    """按配置路径、以及商户证书同目录查找 pub_key.pem。"""
    tried: list[Path] = []
    if explicit_path:
        p = _resolve_path(explicit_path)
        tried.append(p)
        if p.is_file():
            return p

    key_path = _resolve_path(settings.wx_pay_key_path)
    siblings = [
        key_path.parent / "pub_key.pem",
        key_path.parent / "wechatpay_public_key.pem",
        _BACKEND_ROOT / "cert" / "pub_key.pem",
        _BACKEND_ROOT / "certs" / "pub_key.pem",
    ]
    for p in siblings:
        tried.append(p)
        if p.is_file():
            return p
    logger.error("微信支付公钥文件未找到，已尝试: %s", [str(p) for p in tried])
    return None


@lru_cache(maxsize=1)
def _get_client() -> WeChatPay:
    key_path = _resolve_path(settings.wx_pay_key_path)
    if not key_path.is_file():
        raise RuntimeError(f"微信支付私钥不存在: {key_path}")

    cert_dir = str(key_path.parent)
    notify_url = f"{settings.base_url.rstrip('/')}/api/payment/wechat/notify"

    kwargs: dict = {
        "wechatpay_type": WeChatPayType.MINIPROG,
        "mchid": settings.wx_pay_mchid,
        "private_key": key_path.read_text(encoding="utf-8"),
        "cert_serial_no": settings.wx_pay_serial_no,
        "apiv3_key": settings.wx_pay_api_v3_key,
        "appid": settings.wx_appid,
        "notify_url": notify_url,
        "cert_dir": cert_dir,
        "logger": logger,
        "partner_mode": False,
    }

    # 商户启用「微信支付公钥」后，验签必须用公钥，否则会报 PUB_KEY_ID_ 解析失败
    public_key_id = (settings.wx_pay_public_key_id or "").strip()
    if public_key_id:
        pub_path = _find_public_key_file(settings.wx_pay_public_key_path)
        if not pub_path:
            raise RuntimeError(
                "已配置 WX_PAY_PUBLIC_KEY_ID，但找不到 pub_key.pem。"
                f"请放到 {_BACKEND_ROOT / 'cert' / 'pub_key.pem'} 或与 apiclient_key.pem 同目录。"
            )
        kwargs["public_key"] = pub_path.read_text(encoding="utf-8")
        kwargs["public_key_id"] = public_key_id
        logger.warning(
            "wechat pay public-key mode enabled: id=%s file=%s",
            public_key_id,
            pub_path,
        )
    else:
        logger.warning(
            "wechat pay: WX_PAY_PUBLIC_KEY_ID 未配置；若商户为公钥模式，购卡会报 PUB_KEY_ID_ 错误"
        )

    return WeChatPay(**kwargs)


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
        try:
            code, message = wxpay.pay(
                description=description,
                out_trade_no=order_no,
                amount={"total": _amount_fen(amount), "currency": "CNY"},
                payer={"openid": openid},
                attach=attach,
                pay_type=WeChatPayType.MINIPROG,
            )
        except ValueError as exc:
            if "PUB_KEY_ID_" in str(exc):
                raise RuntimeError(
                    "微信支付验签失败：商户为公钥模式，请配置 WX_PAY_PUBLIC_KEY_ID "
                    "与 WX_PAY_PUBLIC_KEY_PATH（公钥文件）后重启服务"
                ) from exc
            raise RuntimeError(f"微信支付异常: {exc}") from exc
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
    def query_order(order_no: str) -> dict | None:
        """主动查询微信支付订单状态（回调延迟时用于确认入账）。"""
        if _is_mock_mode():
            return {
                "out_trade_no": order_no,
                "trade_state": "NOTPAY",
                "attach": None,
                "amount_total": None,
            }

        wxpay = _get_client()
        code, message = wxpay.query(out_trade_no=order_no)
        if code != 200:
            logger.warning("wechat query failed: order=%s code=%s message=%s", order_no, code, message)
            return None

        data = json.loads(message)
        amount = data.get("amount") or {}
        amount_total = amount.get("payer_total")
        if amount_total is None:
            amount_total = amount.get("total")
        return {
            "out_trade_no": data.get("out_trade_no"),
            "trade_state": data.get("trade_state"),
            "attach": data.get("attach"),
            "amount_total": amount_total,
        }

    @staticmethod
    def verify_notify(headers: dict, body: bytes) -> dict | None:
        if _is_mock_mode():
            return {"out_trade_no": "", "trade_state": "SUCCESS", "amount_total": None}

        wxpay = _get_client()
        result = wxpay.callback(headers, body)
        if not result:
            return None

        resource = result.get("resource") or {}
        trade_state = resource.get("trade_state")
        if trade_state != "SUCCESS" and result.get("event_type") != "TRANSACTION.SUCCESS":
            return None

        amount = resource.get("amount") or {}
        # payer_total=实付（含优惠后），total=订单金额；优先校验实付
        amount_total = amount.get("payer_total")
        if amount_total is None:
            amount_total = amount.get("total")

        return {
            "out_trade_no": resource.get("out_trade_no"),
            "trade_state": trade_state or "SUCCESS",
            "attach": resource.get("attach"),
            "amount_total": amount_total,
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
