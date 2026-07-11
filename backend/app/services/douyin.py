"""抖音官方团购核销（prepare + verify）。"""

from __future__ import annotations

import logging
import time
from datetime import date, datetime
from urllib.parse import quote

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_API_BASE = "https://open.douyin.com"
_token_cache: dict[str, float | str] = {"token": "", "expires_at": 0.0}


def use_douyin_official() -> bool:
    """抖音核销走官方 API 还是云老板。"""
    provider = (settings.douyin_coupon_provider or "auto").lower()
    has_creds = bool(settings.douyin_client_key and settings.douyin_client_secret and settings.douyin_poi_id)
    if provider == "official":
        return has_creds
    if provider == "yunlaoban":
        return False
    return has_creds


def normalize_coupon_input(raw: str) -> str:
    """去掉券码中的空格、横线等分隔符。"""
    return "".join(ch for ch in (raw or "").strip() if ch.isalnum())


def _looks_like_encrypted_data(raw: str) -> bool:
    text = (raw or "").strip()
    if not text:
        return False
    if text.startswith("http://") or text.startswith("https://"):
        return True
    if "object_id=" in text or "encrypted_data=" in text:
        return True
    # 抖音 object_id 通常较长且含 +/=
    return len(text) > 32 and any(c in text for c in "+/=")


def _extract_encrypted_data(raw: str) -> str:
    text = (raw or "").strip()
    if "object_id=" in text or "encrypted_data=" in text:
        from urllib.parse import parse_qs, urlparse

        parsed = urlparse(text)
        qs = parse_qs(parsed.query)
        if qs.get("object_id"):
            return qs["object_id"][0]
        if qs.get("encrypted_data"):
            return qs["encrypted_data"][0]
    return text


async def _resolve_encrypted_data(client: httpx.AsyncClient, raw: str) -> str:
    """抖音短链需跟随跳转，从最终 URL 的 object_id 取 encrypted_data。"""
    text = (raw or "").strip()
    if not _looks_like_encrypted_data(text):
        return text

    if text.startswith("http://") or text.startswith("https://"):
        url = text
    elif "douyin.com" in text or "iesdouyin.com" in text:
        url = f"https://{text.lstrip('/')}"
    else:
        return _extract_encrypted_data(text)

    try:
        resp = await client.get(url, follow_redirects=True)
        return _extract_encrypted_data(str(resp.url))
    except httpx.HTTPError as e:
        logger.warning("resolve douyin short url failed: %s", e)
        return _extract_encrypted_data(url)


def _api_error(payload: dict, *, fallback: str = "抖音接口错误") -> str:
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    extra = payload.get("extra") if isinstance(payload.get("extra"), dict) else {}
    code = data.get("error_code") or extra.get("error_code")
    known = {
        2190004: "应用未开通对应能力，请在开放平台申请团购核销/门店管理",
        2190005: "应用未获商家授权，请在抖音来客授权「知行岛团购核销」",
        2119005: "应用未获商家授权，请在抖音来客授权「知行岛团购核销」",
        3000002: "所选门店不在该团购的适用门店列表，请在来客检查团购商品的适用门店",
        3000001: "券码无效或已使用，请换一张未核销的券重试",
    }
    if code in known:
        return known[code]
    for block in (data, extra, payload):
        if not isinstance(block, dict):
            continue
        for key in ("description", "sub_description", "message"):
            msg = block.get(key)
            if msg:
                return str(msg)
        code = block.get("error_code")
        if code not in (None, 0, "0"):
            return f"{fallback}（{code}）"
    return fallback


class DouyinService:
    @staticmethod
    async def _get_client_token(client: httpx.AsyncClient) -> str:
        now = time.time()
        cached = _token_cache.get("token")
        expires_at = float(_token_cache.get("expires_at") or 0)
        if cached and now < expires_at - 120:
            return str(cached)

        resp = await client.post(
            f"{_API_BASE}/oauth/client_token/",
            json={
                "grant_type": "client_credential",
                "client_key": settings.douyin_client_key,
                "client_secret": settings.douyin_client_secret,
            },
        )
        payload = resp.json()
        data = payload.get("data") or {}
        if data.get("error_code") not in (0, None):
            raise ValueError(_api_error(payload, fallback="获取抖音 access_token 失败"))

        token = data.get("access_token") or ""
        if not token:
            raise ValueError("抖音 access_token 为空")

        expires_in = int(data.get("expires_in") or 7200)
        _token_cache["token"] = token
        _token_cache["expires_at"] = now + max(expires_in - 60, 300)
        return token

    @staticmethod
    async def _prepare_with_client(client: httpx.AsyncClient, code: str) -> dict:
        token = await DouyinService._get_client_token(client)
        params: dict[str, str] = {"poi_id": str(settings.douyin_poi_id)}
        raw = (code or "").strip()
        if _looks_like_encrypted_data(raw):
            encrypted = await _resolve_encrypted_data(client, raw)
            params["encrypted_data"] = quote(encrypted, safe="")
        else:
            params["code"] = normalize_coupon_input(raw)

        resp = await client.get(
            f"{_API_BASE}/goodlife/v1/fulfilment/certificate/prepare/",
            headers={"access-token": token, "content-type": "application/json"},
            params=params,
        )
        payload = resp.json()
        data = payload.get("data") or {}
        if data.get("error_code") not in (0, None):
            raise ValueError(_api_error(payload, fallback="验券准备失败"))

        certificates = data.get("certificates_v2") or data.get("certificates") or []
        if not certificates:
            raise ValueError("未找到可用券码，请确认券未使用或已过期")

        cert = certificates[0]
        encrypted_code = cert.get("encrypted_code") or ""
        if not encrypted_code:
            raise ValueError("验券准备未返回 encrypted_code")

        sku = cert.get("sku") or {}
        title = sku.get("title") or sku.get("product_name") or "抖音团购"
        deal_id = str(sku.get("sku_id") or sku.get("product_id") or "")

        expire_date = None
        expire_raw = cert.get("expire_time")
        if expire_raw is not None:
            try:
                ts = float(expire_raw)
                if ts > 1e12:
                    ts /= 1000.0
                expire_date = datetime.fromtimestamp(ts).date()
            except (ValueError, OSError, OverflowError):
                expire_date = None

        return {
            "verify_token": data.get("verify_token") or "",
            "encrypted_code": encrypted_code,
            "order_id": data.get("order_id"),
            "ticketName": title,
            "ticketData": {
                "dealId": deal_id,
                "dealTitle": title,
                "receiptCode": normalize_coupon_input(raw) or raw,
                "sku_id": sku.get("sku_id"),
                "product_id": sku.get("product_id"),
                "expire_time": expire_raw,
                "receiptEndDate": str(expire_date) if expire_date else None,
            },
            "raw_prepare": data,
        }

    @staticmethod
    async def _verify_with_client(client: httpx.AsyncClient, prepared: dict) -> dict:
        token = await DouyinService._get_client_token(client)
        body = {
            "verify_token": prepared["verify_token"],
            "poi_id": str(settings.douyin_poi_id),
            "encrypted_codes": [prepared["encrypted_code"]],
        }
        resp = await client.post(
            f"{_API_BASE}/goodlife/v1/fulfilment/certificate/verify/",
            headers={"access-token": token, "content-type": "application/json"},
            json=body,
        )
        payload = resp.json()
        data = payload.get("data") or {}
        if data.get("error_code") not in (0, None):
            raise ValueError(_api_error(payload, fallback="核销失败"))

        results = data.get("verify_results") or []
        if not results:
            raise ValueError("核销未返回结果")

        result = results[0]
        result_code = result.get("result")
        if result_code not in (0, 2, 1208):
            msg = result.get("msg") or "核销失败"
            raise ValueError(msg)

        return {"verify_result": result, "raw_verify": data}

    @staticmethod
    async def prepare_and_verify(code: str) -> tuple[dict, str]:
        """对齐云老板返回结构，供 exchange 复用。"""
        import json

        timeout = settings.yunlaoban_timeout_sec
        async with httpx.AsyncClient(timeout=timeout) as client:
            prepared = await DouyinService._prepare_with_client(client, code)
            verified = await DouyinService._verify_with_client(client, prepared)

        yunlaoban_shape = {
            "ticketInfo": prepared.get("verify_token") or "",
            "ticketName": prepared.get("ticketName") or "",
            "ticketData": prepared.get("ticketData") or {},
        }
        consume_result = json.dumps(verified, ensure_ascii=False)
        return yunlaoban_shape, consume_result


def parse_douyin_voucher_expire_date(ticket_data: dict | None) -> date | None:
    if not ticket_data:
        return None
    for key in ("receiptEndDate", "expire_time"):
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
