import json

import httpx

from app.core.config import settings


def _use_mock() -> bool:
    """mock / meituan / auto：auto 时无凭证则走 Mock。"""
    provider = (settings.coupon_provider or "auto").lower()
    if provider == "mock":
        return True
    if provider == "meituan":
        return not settings.yunlaoban_client_id
    return not settings.yunlaoban_client_id


class YunlaobanService:
    @staticmethod
    def _headers():
        return {
            "Content-Type": "application/json",
            "clientId": settings.yunlaoban_client_id,
            "secret": settings.yunlaoban_secret,
        }

    @staticmethod
    async def prepare(platform: int, code: str) -> dict:
        if _use_mock():
            return _mock_prepare(code, platform)
        shop_id = int(settings.yunlaoban_shop_id)
        base = settings.yunlaoban_base_url.rstrip("/")
        async with httpx.AsyncClient(timeout=settings.yunlaoban_timeout_sec) as client:
            resp = await client.post(
                f"{base}/api/isp/groupBuy/prepare",
                headers=YunlaobanService._headers(),
                json={"shopId": shop_id, "platform": platform, "code": code},
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
        }

    @staticmethod
    async def consume(platform: int, code: str, ticket_info: str) -> str:
        if _use_mock():
            return json.dumps({"mock": True, "code": code})
        shop_id = int(settings.yunlaoban_shop_id)
        base = settings.yunlaoban_base_url.rstrip("/")
        async with httpx.AsyncClient(timeout=settings.yunlaoban_timeout_sec) as client:
            resp = await client.post(
                f"{base}/api/isp/groupBuy/consumeWithResult",
                headers=YunlaobanService._headers(),
                json={
                    "shopId": shop_id,
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
