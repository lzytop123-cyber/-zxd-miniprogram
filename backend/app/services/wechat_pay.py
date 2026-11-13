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
from app.services.pay_account import ResolvedPayAccount, default_pay_account

logger = logging.getLogger(__name__)

# backend/ 根目录（不依赖 systemd 的 WorkingDirectory）
_BACKEND_ROOT = Path(__file__).resolve().parents[2]


def _amount_fen(amount: Decimal) -> int:
    return int((amount * 100).quantize(Decimal("1")))


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


def _find_public_key_file(explicit_path: str, key_path: str) -> Path | None:
    tried: list[Path] = []
    if explicit_path:
        p = _resolve_path(explicit_path)
        tried.append(p)
        if p.is_file():
            return p

    key = _resolve_path(key_path)
    siblings = [
        key.parent / "pub_key.pem",
        key.parent / "wechatpay_public_key.pem",
        _BACKEND_ROOT / "cert" / "pub_key.pem",
        _BACKEND_ROOT / "certs" / "pub_key.pem",
    ]
    for p in siblings:
        tried.append(p)
        if p.is_file():
            return p
    logger.error("微信支付公钥文件未找到，已尝试: %s", [str(p) for p in tried])
    return None


def _use_mock(account: ResolvedPayAccount) -> bool:
    """开发环境始终 mock；默认账户未配置 mchid 时也 mock。绑定账户在非开发环境走真实支付。"""
    if settings.app_env == "development":
        return True
    if account.source == "default" and not (settings.wx_pay_mchid or "").strip():
        return True
    return False


def _build_client(account: ResolvedPayAccount) -> WeChatPay:
    key_path = _resolve_path(account.key_path)
    if not key_path.is_file():
        raise RuntimeError(f"微信支付私钥不存在: {key_path}")

    cert_dir = str(key_path.parent)
    notify_url = f"{settings.base_url.rstrip('/')}/api/payment/wechat/notify"

    kwargs: dict = {
        "wechatpay_type": WeChatPayType.MINIPROG,
        "mchid": account.mchid,
        "private_key": key_path.read_text(encoding="utf-8"),
        "cert_serial_no": account.serial_no,
        "apiv3_key": account.api_v3_key,
        "appid": settings.wx_appid,
        "notify_url": notify_url,
        "cert_dir": cert_dir,
        "logger": logger,
        "partner_mode": False,
    }

    public_key_id = (account.public_key_id or "").strip()
    if public_key_id:
        pub_path = _find_public_key_file(account.public_key_path, account.key_path)
        if not pub_path:
            raise RuntimeError(
                "已配置公钥模式，但找不到 pub_key.pem。"
                f"请放到 {_BACKEND_ROOT / 'cert' / 'pub_key.pem'} 或与私钥同目录。"
            )
        kwargs["public_key"] = pub_path.read_text(encoding="utf-8")
        kwargs["public_key_id"] = public_key_id

    return WeChatPay(**kwargs)


@lru_cache(maxsize=16)
def _get_client_cached(
    mchid: str,
    serial_no: str,
    api_v3_key: str,
    key_path: str,
    public_key_id: str,
    public_key_path: str,
) -> WeChatPay:
    account = ResolvedPayAccount(
        mchid=mchid,
        source="bound",
        serial_no=serial_no,
        api_v3_key=api_v3_key,
        key_path=key_path,
        public_key_id=public_key_id,
        public_key_path=public_key_path,
    )
    return _build_client(account)


def _client_for(account: ResolvedPayAccount) -> WeChatPay:
    return _get_client_cached(
        account.mchid,
        account.serial_no,
        account.api_v3_key,
        account.key_path,
        account.public_key_id or "",
        account.public_key_path or "",
    )


def _parse_notify_resource(result: dict) -> dict | None:
    if not result:
        return None
    resource = result.get("resource") or {}
    trade_state = resource.get("trade_state")
    if trade_state != "SUCCESS" and result.get("event_type") != "TRANSACTION.SUCCESS":
        return None
    amount = resource.get("amount") or {}
    amount_total = amount.get("payer_total")
    if amount_total is None:
        amount_total = amount.get("total")
    return {
        "out_trade_no": resource.get("out_trade_no"),
        "success_time": resource.get("success_time"),
        "trade_state": trade_state or "SUCCESS",
        "attach": resource.get("attach"),
        "amount_total": amount_total,
        "mchid": resource.get("mchid") or result.get("mchid"),
    }


class WechatPayService:
    """微信支付 v3 封装（支持多商户；开发环境返回模拟参数）"""

    @staticmethod
    def create_jsapi_order(
        order_no: str,
        amount: Decimal,
        openid: str,
        description: str,
        attach: str | None = None,
        pay_account: ResolvedPayAccount | None = None,
    ) -> dict:
        account = pay_account or default_pay_account()
        if _use_mock(account):
            nonce = secrets.token_hex(16)
            timestamp = str(int(time.time()))
            return {
                "timeStamp": timestamp,
                "nonceStr": nonce,
                "package": f"prepay_id=mock_prepay_{order_no}",
                "signType": "RSA",
                "paySign": hashlib.sha256(f"{order_no}{nonce}".encode()).hexdigest(),
                "mchid": account.mchid,
            }

        wxpay = _client_for(account)
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
                    "微信支付验签失败：商户为公钥模式，请配置公钥 ID 与公钥文件后重启服务"
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
            "mchid": account.mchid,
        }

    @staticmethod
    def query_order(
        order_no: str,
        pay_account: ResolvedPayAccount | None = None,
        mchid: str | None = None,
    ) -> dict | None:
        account = pay_account or default_pay_account()
        if mchid and not pay_account:
            account = ResolvedPayAccount(
                mchid=mchid,
                source="bound" if mchid != default_pay_account().mchid else "default",
                serial_no=account.serial_no,
                api_v3_key=account.api_v3_key,
                cert_path=account.cert_path,
                key_path=account.key_path,
                public_key_id=account.public_key_id,
                public_key_path=account.public_key_path,
            )
        if _use_mock(account):
            return {
                "out_trade_no": order_no,
                "trade_state": "NOTPAY",
                "attach": None,
                "amount_total": None,
                "mchid": account.mchid,
            }

        wxpay = _client_for(account)
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
            "success_time": data.get("success_time"),
            "trade_state": data.get("trade_state"),
            "attach": data.get("attach"),
            "amount_total": amount_total,
            "mchid": data.get("mchid") or account.mchid,
        }

    @staticmethod
    def verify_notify(headers: dict, body: bytes, accounts: list[ResolvedPayAccount] | None = None) -> dict | None:
        candidates = accounts or [default_pay_account()]
        if settings.app_env == "development" or not (settings.wx_pay_mchid or "").strip():
            # mock：无法验签，返回空 out_trade_no 由调用方在开发 mock-pay 路径处理
            if all(_use_mock(a) for a in candidates):
                return {"out_trade_no": "", "trade_state": "SUCCESS", "amount_total": None, "mchid": None}

        last_error: Exception | None = None
        for account in candidates:
            if _use_mock(account):
                continue
            try:
                wxpay = _client_for(account)
                result = wxpay.callback(headers, body)
                parsed = _parse_notify_resource(result) if result else None
                if parsed:
                    if not parsed.get("mchid"):
                        parsed["mchid"] = account.mchid
                    return parsed
            except Exception as exc:
                last_error = exc
                continue
        if last_error:
            logger.warning("wechat notify verify failed: %s", last_error)
        return None

    @staticmethod
    def refund(
        order_no: str,
        refund_amount: Decimal,
        total_amount: Decimal,
        reason: str,
        pay_account: ResolvedPayAccount | None = None,
        mchid: str | None = None,
        *,
        confirmed_refund_no: str | None = None,
    ) -> bool:
        account = pay_account or default_pay_account()
        if mchid and pay_account is None:
            # 仅有快照 mchid：仍用默认证书尝试（历史订单）；新订单应传入完整 account
            if mchid != account.mchid:
                logger.warning(
                    "refund with snapshot mchid=%s but using credentials for %s",
                    mchid,
                    account.mchid,
                )
                account = ResolvedPayAccount(
                    mchid=mchid,
                    source="bound",
                    serial_no=account.serial_no,
                    api_v3_key=account.api_v3_key,
                    cert_path=account.cert_path,
                    key_path=account.key_path,
                    public_key_id=account.public_key_id,
                    public_key_path=account.public_key_path,
                )
        if _use_mock(account):
            return True

        wxpay = _client_for(account)
        out_refund_no = confirmed_refund_no or f"RF{order_no}{int(time.time()) % 100000:05d}"
        if confirmed_refund_no:
            query_code, query_body = wxpay.query_refund(out_refund_no)
            if query_code == 200:
                return json.loads(query_body).get("status") == "SUCCESS"
            if query_code != 404:
                logger.error("wechat refund query failed: code=%s", query_code)
                return False
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
        if confirmed_refund_no:
            return json.loads(message).get("status") == "SUCCESS"
        return True


def resolve_account_for_mchid(db, mchid: str | None) -> ResolvedPayAccount:
    """按订单快照 mchid 找回收款账户；找不到则默认账户。"""
    from app.services.pay_account import list_resolved_accounts_for_notify

    if not mchid:
        return default_pay_account()
    for acc in list_resolved_accounts_for_notify(db):
        if acc.mchid == mchid:
            return acc
    return default_pay_account()
