"""集市内容安全：敏感词 + 微信内容安全接口（msgSecCheck / imgSecCheck）。"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import MarketSensitiveWord
from app.services.business import WechatService

logger = logging.getLogger(__name__)

# 未开通内容安全能力时常见错误码
_NO_PERMISSION_ERRCODES = {48001, 61010, 40066, 40001, 40013}


@dataclass
class SafetyResult:
    ok: bool
    reason: str | None = None
    hit_level: str | None = None  # block | review
    # 便于审核录屏/日志举证
    provider: str | None = None  # local | wechat_msg | wechat_img | disabled
    wechat: dict[str, Any] = field(default_factory=dict)


def check_sensitive_words(db: Session, text: str) -> SafetyResult:
    content = (text or "").strip()
    if not content:
        return SafetyResult(ok=True, provider="local")
    words = db.scalars(
        select(MarketSensitiveWord).where(MarketSensitiveWord.status == 1)
    ).all()
    for row in words:
        if row.word and row.word in content:
            if row.level == "block":
                return SafetyResult(
                    ok=False, reason="内容包含违规词", hit_level="block", provider="local"
                )
            return SafetyResult(
                ok=True, reason="需人工复核", hit_level="review", provider="local"
            )
    return SafetyResult(ok=True, provider="local")


async def wechat_msg_sec_check(*, openid: str, content: str) -> SafetyResult:
    """调用微信 msgSecCheck。启用后必须真正请求微信；未开通能力会明确失败。"""
    if not settings.wx_content_security_enabled:
        return SafetyResult(ok=True, reason="content_security_disabled", provider="disabled")
    text = (content or "").strip()
    if not text:
        return SafetyResult(ok=True, provider="wechat_msg")
    try:
        token = await WechatService.get_access_token()
        url = f"https://api.weixin.qq.com/wxa/msg_sec_check?access_token={token}"
        payload = {
            "openid": openid,
            "scene": 3,  # 论坛场景
            "version": 2,
            "content": text[:2500],
        }
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.post(url, json=payload)
            data = resp.json()
        errcode = data.get("errcode", -1)
        trace = {
            "api": "msgSecCheck",
            "errcode": errcode,
            "errmsg": data.get("errmsg"),
            "result": data.get("result"),
            "detail": data.get("detail"),
            "trace_id": data.get("trace_id"),
        }
        logger.info("msg_sec_check done errcode=%s suggest=%s", errcode, (data.get("result") or {}).get("suggest"))
        if errcode == 0:
            result = (data.get("result") or {}).get("suggest") or "pass"
            if result == "risky":
                return SafetyResult(
                    ok=False,
                    reason="微信内容安全未通过",
                    hit_level="block",
                    provider="wechat_msg",
                    wechat=trace,
                )
            if result == "review":
                return SafetyResult(
                    ok=True,
                    reason="需人工复核",
                    hit_level="review",
                    provider="wechat_msg",
                    wechat=trace,
                )
            return SafetyResult(ok=True, provider="wechat_msg", wechat=trace)
        if errcode == 87014:
            return SafetyResult(
                ok=False,
                reason="内容未通过安全检测",
                hit_level="block",
                provider="wechat_msg",
                wechat=trace,
            )
        if errcode in _NO_PERMISSION_ERRCODES:
            return SafetyResult(
                ok=False,
                reason="请先在微信公众平台开通「内容安全」接口权限",
                hit_level="block",
                provider="wechat_msg",
                wechat=trace,
            )
        # 启用后不再静默放行未知错误，避免审核误以为未接入
        return SafetyResult(
            ok=False,
            reason=f"内容安全检测异常({errcode})，请稍后重试",
            hit_level="review",
            provider="wechat_msg",
            wechat=trace,
        )
    except Exception as exc:
        logger.warning("msg_sec_check failed: %s", exc)
        return SafetyResult(
            ok=False,
            reason="内容安全服务暂时不可用，请稍后重试",
            hit_level="review",
            provider="wechat_msg",
            wechat={"api": "msgSecCheck", "error": exc.__class__.__name__},
        )


async def wechat_img_sec_check(*, image_bytes: bytes, filename: str = "image.jpg") -> SafetyResult:
    """调用微信 imgSecCheck（同步）。单图建议 ≤1MB。"""
    if not settings.wx_content_security_enabled:
        return SafetyResult(ok=True, reason="content_security_disabled", provider="disabled")
    if not image_bytes:
        return SafetyResult(ok=True, provider="wechat_img")
    if len(image_bytes) > 1_000_000:
        logger.info("img_sec_check skipped: image too large for sync api (%s bytes)", len(image_bytes))
        return SafetyResult(
            ok=False,
            reason="图片过大无法机审，请压缩至 1MB 以内后再上传",
            hit_level="review",
            provider="wechat_img",
            wechat={"api": "imgSecCheck", "skipped": "too_large"},
        )
    try:
        token = await WechatService.get_access_token()
        url = f"https://api.weixin.qq.com/wxa/img_sec_check?access_token={token}"
        files = {"media": (filename, image_bytes, "application/octet-stream")}
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, files=files)
            data = resp.json()
        errcode = data.get("errcode", -1)
        trace = {
            "api": "imgSecCheck",
            "errcode": errcode,
            "errmsg": data.get("errmsg"),
        }
        logger.info("img_sec_check done errcode=%s", errcode)
        if errcode == 0:
            return SafetyResult(ok=True, provider="wechat_img", wechat=trace)
        if errcode == 87014:
            return SafetyResult(
                ok=False,
                reason="图片未通过安全检测",
                hit_level="block",
                provider="wechat_img",
                wechat=trace,
            )
        if errcode in _NO_PERMISSION_ERRCODES:
            return SafetyResult(
                ok=False,
                reason="请先在微信公众平台开通「内容安全」接口权限",
                hit_level="block",
                provider="wechat_img",
                wechat=trace,
            )
        return SafetyResult(
            ok=False,
            reason=f"图片安全检测异常({errcode})，请稍后重试",
            hit_level="review",
            provider="wechat_img",
            wechat=trace,
        )
    except Exception as exc:
        logger.warning("img_sec_check failed: %s", exc)
        return SafetyResult(
            ok=False,
            reason="图片安全服务暂时不可用，请稍后重试",
            hit_level="review",
            provider="wechat_img",
            wechat={"api": "imgSecCheck", "error": exc.__class__.__name__},
        )


async def check_listing_text(
    db: Session, *, openid: str, title: str, description: str
) -> SafetyResult:
    combined = f"{title}\n{description}"
    local = check_sensitive_words(db, combined)
    if not local.ok:
        return local
    remote = await wechat_msg_sec_check(openid=openid, content=combined)
    if not remote.ok:
        return remote
    if local.hit_level == "review" or remote.hit_level == "review":
        return SafetyResult(
            ok=True,
            hit_level="review",
            reason="需人工复核",
            provider=remote.provider or local.provider,
            wechat=remote.wechat,
        )
    return SafetyResult(ok=True, provider=remote.provider, wechat=remote.wechat)


def safety_to_audit_dict(result: SafetyResult) -> dict[str, Any]:
    return {
        "ok": result.ok,
        "reason": result.reason,
        "hit_level": result.hit_level,
        "provider": result.provider,
        "wechat": result.wechat or None,
        "enabled": bool(settings.wx_content_security_enabled),
    }
