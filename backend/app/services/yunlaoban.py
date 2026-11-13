import json
import logging
from datetime import date, datetime

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


def _use_mock() -> bool:
    """mock / meituan / auto：auto 时无凭证则走 Mock。"""
    provider = (settings.coupon_provider or "auto").lower()
    if provider == "mock":
        return True
    if provider == "meituan":
        return not settings.yunlaoban_client_id
    return not settings.yunlaoban_client_id


def parse_voucher_expire_date(ticket_data: dict | None) -> date | None:
    """团购券自身有效期（须在此时前核销），来自云老板 ticketData.receiptEndDate 等。"""
    if not ticket_data:
        return None
    for key in ("receiptEndDate", "receipt_end_date", "couponEndTime", "expireTime", "expire_time"):
        raw = ticket_data.get(key)
        if raw is None:
            continue
        try:
            if isinstance(raw, (int, float)):
                ts = float(raw)
                if ts > 1e12:
                    ts /= 1000.0
                return datetime.fromtimestamp(ts).date()
            text = str(raw).strip()
            if not text:
                continue
            if text.isdigit():
                ts = float(text)
                if ts > 1e12:
                    ts /= 1000.0
                return datetime.fromtimestamp(ts).date()
            return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
        except (ValueError, OSError, OverflowError):
            continue
    return None


def resolve_yunlaoban_shop_id(store_shop_id: str | None = None) -> int:
    """
    门店 meituan_shop_id 优先，否则回退全局 MEITUAN_SHOP_ID。
    同一套 clientId/secret 下可按门店切换 shopId。
    """
    raw = (store_shop_id or "").strip() or (settings.yunlaoban_shop_id or "").strip()
    if not raw:
        raise ValueError("未配置美团/云老板门店 shopId，请在门店资料或环境变量中填写")
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"shopId 无效: {raw}") from exc


class YunlaobanService:
    @staticmethod
    def _headers():
        return {
            "Content-Type": "application/json",
            "clientId": settings.yunlaoban_client_id,
            "secret": settings.yunlaoban_secret,
        }

    @staticmethod
    def _api_base() -> str:
        return settings.yunlaoban_base_url.rstrip("/")

    @staticmethod
    async def _prepare_with_client(
        client: httpx.AsyncClient,
        platform: int,
        code: str,
        shop_id: int | None = None,
    ) -> dict:
        sid = shop_id if shop_id is not None else resolve_yunlaoban_shop_id()
        resp = await client.post(
            f"{YunlaobanService._api_base()}/api/isp/groupBuy/prepare",
            headers=YunlaobanService._headers(),
            json={"shopId": sid, "platform": platform, "code": code},
        )
        data = resp.json()
        if data.get("code") != "SUCCESS":
            raise ValueError(data.get("message", "验券失败"))
        ticket = json.loads(data["result"])
        ticket_data = json.loads(ticket["ticketData"])
        return {
            "ticketInfo": ticket["ticketInfo"],
            "ticketName": ticket.get("ticketName", ""),
            "ticketData": ticket_data,
            "payAmount": ticket.get("payAmount"),
            "shopId": sid,
        }

    @staticmethod
    async def _consume_with_client(
        client: httpx.AsyncClient,
        platform: int,
        code: str,
        ticket_info: str,
        shop_id: int | None = None,
    ) -> str:
        sid = shop_id if shop_id is not None else resolve_yunlaoban_shop_id()
        resp = await client.post(
            f"{YunlaobanService._api_base()}/api/isp/groupBuy/consumeWithResult",
            headers=YunlaobanService._headers(),
            json={
                "shopId": sid,
                "platform": platform,
                "code": code,
                "ticketInfo": ticket_info,
                "num": 1,
            },
        )
        data = resp.json()
        if data.get("code") != "SUCCESS":
            raise ValueError(data.get("message", "核销失败"))
        return data.get("result") or "true"

    @staticmethod
    async def prepare(platform: int, code: str, shop_id: str | int | None = None) -> dict:
        if _use_mock():
            if settings.app_env == "production" and (settings.coupon_provider or "").lower() == "meituan":
                logger.warning("COUPON_PROVIDER=meituan but Yunlaoban credentials missing; using mock prepare")
            return _mock_prepare(code, platform)
        resolved = resolve_yunlaoban_shop_id(str(shop_id) if shop_id is not None else None)
        async with httpx.AsyncClient(timeout=settings.yunlaoban_timeout_sec) as client:
            return await YunlaobanService._prepare_with_client(client, platform, code, shop_id=resolved)

    @staticmethod
    async def consume(
        platform: int,
        code: str,
        ticket_info: str,
        shop_id: str | int | None = None,
    ) -> str:
        if _use_mock():
            return json.dumps({"mock": True, "code": code})
        resolved = resolve_yunlaoban_shop_id(str(shop_id) if shop_id is not None else None)
        async with httpx.AsyncClient(timeout=settings.yunlaoban_timeout_sec) as client:
            return await YunlaobanService._consume_with_client(
                client, platform, code, ticket_info, shop_id=resolved
            )

    @staticmethod
    async def prepare_and_consume(
        platform: int,
        code: str,
        shop_id: str | int | None = None,
    ) -> tuple[dict, str]:
        """复用同一 HTTP 连接，减少 prepare + consume 两次往返的握手开销。"""
        if _use_mock():
            prepared = _mock_prepare(code, platform)
            return prepared, json.dumps({"mock": True, "code": code})
        resolved = resolve_yunlaoban_shop_id(str(shop_id) if shop_id is not None else None)
        async with httpx.AsyncClient(timeout=settings.yunlaoban_timeout_sec) as client:
            prepared = await YunlaobanService._prepare_with_client(
                client, platform, code, shop_id=resolved
            )
            consume_result = await YunlaobanService._consume_with_client(
                client, platform, code, prepared["ticketInfo"], shop_id=resolved
            )
            return prepared, consume_result


def _mock_prepare(code: str, platform: int) -> dict:
    """开发环境：券码末位映射不同权益类型"""
    mapping = {
        "1": ("100001", "知行岛4小时畅学券", "hours", 4),
        "2": ("100002", "知行岛天卡", "day_pass", 1),
        "3": ("100004", "知行岛月卡", "month_pass", 30),
        "4": ("100005", "知行岛晚自习月卡", "night_monthly", 30),
        "5": ("100007", "知行岛10次卡", "session", 10),
    }
    key = code[-1] if code else "1"
    deal_id, name, reward_type, value = mapping.get(key, mapping["1"])
    return {
        "ticketInfo": f"mock_ticket_{code}",
        "ticketName": name,
        "ticketData": {
            "dealId": deal_id,
            "dealTitle": name,
            "receiptCode": code,
            "dealPrice": 39.0,
        },
    }
