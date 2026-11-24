"""云飞 API（来客核销）团购验券/核销。

文档：https://doc.yunfeiapi.com/8949219m0
仅用于按门店配置 coupon_provider=yunfei 的门店；千峰等仍走云老板。
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_token_cache: dict[str, Any] = {"access_token": "", "expires_at": 0.0}


def yunfei_configured() -> bool:
    return bool((settings.yunfei_app_id or "").strip() and (settings.yunfei_app_secret or "").strip())


def _platform_name(platform: int) -> str:
    return "douyin" if int(platform) == 2 else "meituan"


def _base() -> str:
    return (settings.yunfei_base_url or "http://wspacebot.yunfeiwork.com").rstrip("/")


def _raise_biz(data: dict) -> None:
    code = data.get("code")
    if code in (200, "200", "SUCCESS"):
        return
    msg = data.get("msg") or data.get("message") or "云飞接口调用失败"
    raise ValueError(str(msg))


class YunfeiService:
    @staticmethod
    async def _get_access_token(client: httpx.AsyncClient) -> str:
        now = time.time()
        cached = (_token_cache.get("access_token") or "").strip()
        expires_at = float(_token_cache.get("expires_at") or 0)
        # 提前 1 天刷新（官方建议）
        if cached and expires_at - now > 86400:
            return cached

        if not yunfei_configured():
            raise ValueError("未配置云飞 appId/appSecret，请在环境变量中填写 YUNFEI_APP_ID / YUNFEI_APP_SECRET")

        resp = await client.post(
            f"{_base()}/wspace-openapi/oauth/token",
            headers={"Content-Type": "application/json"},
            json={
                "appId": settings.yunfei_app_id.strip(),
                "appSecret": settings.yunfei_app_secret.strip(),
            },
        )
        data = resp.json()
        _raise_biz(data)
        payload = data.get("data") or {}
        token = (payload.get("accessToken") or payload.get("access_token") or "").strip()
        if not token:
            raise ValueError("云飞 accessToken 为空")
        expires_in = int(payload.get("expiresIn") or payload.get("expires_in") or 2592000)
        _token_cache["access_token"] = token
        _token_cache["expires_at"] = now + max(expires_in - 86400, 3600)
        return token

    @staticmethod
    def _normalize_prepare(code: str, data: dict, op_poi_id: str) -> dict:
        """整理成与云老板 prepare 相近的结构，供兑换发卡逻辑复用。"""
        result0: dict = {}
        results = data.get("result")
        if isinstance(results, list) and results and isinstance(results[0], dict):
            result0 = results[0]

        deal_id = data.get("dealId") or result0.get("dealId") or data.get("skuId") or result0.get("skuId") or ""
        deal_title = data.get("dealTitle") or result0.get("dealTitle") or ""
        deal_price = result0.get("dealPrice")
        if deal_price is None and data.get("payAmount") is not None:
            try:
                # 云飞示例 payAmount 多为分
                pay_raw = float(data.get("payAmount"))
                deal_price = pay_raw / 100.0 if pay_raw >= 100 else pay_raw
            except (TypeError, ValueError):
                deal_price = None

        verify_count = int(data.get("verifyCount") or 1)
        receipt_code = data.get("receiptCode") or result0.get("receiptCode") or code
        ticket_info = json.dumps(
            {
                "opPoiId": op_poi_id,
                "receiptCode": receipt_code,
                "verifyCount": verify_count,
            },
            ensure_ascii=False,
        )
        pay_amount = deal_price
        if pay_amount is None and data.get("payAmount") is not None:
            try:
                raw = float(data["payAmount"])
                pay_amount = raw / 100.0 if raw >= 100 else raw
            except (TypeError, ValueError):
                pay_amount = None

        return {
            "ticketInfo": ticket_info,
            "ticketName": str(deal_title or ""),
            "ticketData": {
                "dealId": str(deal_id),
                "dealTitle": str(deal_title or ""),
                "dealGroupId": data.get("dealGroupId") or result0.get("dealGroupId"),
                "receiptCode": str(receipt_code),
                "receiptEndDate": data.get("receiptEndDate"),
                "dealPrice": deal_price,
                "orderId": data.get("orderId") or result0.get("orderId"),
            },
            "payAmount": pay_amount,
            "_yunfei_prepare": data,
            "_yunfei_op_poi_id": op_poi_id,
            "_yunfei_verify_count": verify_count,
        }

    @staticmethod
    async def _receipt(
        client: httpx.AsyncClient,
        *,
        code: str,
        op_poi_id: str,
        platform: int,
        typ: str,
        verify_count: int | None = None,
    ) -> dict:
        token = await YunfeiService._get_access_token(client)
        body: dict[str, Any] = {
            "opPoiId": str(op_poi_id).strip(),
            "receiptCode": code,
            "platform": _platform_name(platform),
            "type": str(typ),
        }
        if typ == "2":
            body["verifyCount"] = int(verify_count or 1)
        resp = await client.post(
            f"{_base()}/wspace-openapi/partner/tuangou/receipt/consume",
            params={"access_token": token},
            headers={"Content-Type": "application/json"},
            json=body,
        )
        data = resp.json()
        _raise_biz(data)
        payload = data.get("data")
        if not isinstance(payload, dict):
            raise ValueError(data.get("msg") or "云飞返回数据异常")
        return payload

    @staticmethod
    async def prepare(platform: int, code: str, op_poi_id: str) -> dict:
        oid = (op_poi_id or "").strip()
        if not oid:
            raise ValueError("该门店未配置云飞 opPoiId（请在门店「美团门店 ID」填写云飞门店 ID）")
        timeout = settings.yunfei_timeout_ms / 1000.0
        async with httpx.AsyncClient(timeout=timeout) as client:
            raw = await YunfeiService._receipt(
                client, code=code, op_poi_id=oid, platform=platform, typ="1"
            )
            return YunfeiService._normalize_prepare(code, raw, oid)

    @staticmethod
    async def consume(platform: int, code: str, prepared: dict) -> str:
        oid = (prepared.get("_yunfei_op_poi_id") or "").strip()
        if not oid:
            try:
                info = json.loads(prepared.get("ticketInfo") or "{}")
                oid = str(info.get("opPoiId") or "").strip()
            except Exception:
                oid = ""
        if not oid:
            raise ValueError("云飞核销缺少门店 opPoiId，请重新验券")
        verify_count = prepared.get("_yunfei_verify_count")
        if verify_count is None:
            try:
                info = json.loads(prepared.get("ticketInfo") or "{}")
                verify_count = info.get("verifyCount") or 1
            except Exception:
                verify_count = 1
        timeout = settings.yunfei_timeout_ms / 1000.0
        async with httpx.AsyncClient(timeout=timeout) as client:
            raw = await YunfeiService._receipt(
                client,
                code=code,
                op_poi_id=oid,
                platform=platform,
                typ="2",
                verify_count=int(verify_count or 1),
            )
            return json.dumps(raw, ensure_ascii=False)
