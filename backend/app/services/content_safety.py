"""集市内容安全：敏感词 + 可选微信内容安全接口。"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import MarketSensitiveWord
from app.services.business import WechatService

logger = logging.getLogger(__name__)


@dataclass
class SafetyResult:
    ok: bool
    reason: str | None = None
    hit_level: str | None = None  # block | review


def check_sensitive_words(db: Session, text: str) -> SafetyResult:
    content = (text or "").strip()
    if not content:
        return SafetyResult(ok=True)
    words = db.scalars(
        select(MarketSensitiveWord).where(MarketSensitiveWord.status == 1)
    ).all()
    for row in words:
        if row.word and row.word in content:
            if row.level == "block":
                return SafetyResult(ok=False, reason="内容包含违规词", hit_level="block")
            return SafetyResult(ok=True, reason="需人工复核", hit_level="review")
    return SafetyResult(ok=True)


async def wechat_msg_sec_check(*, openid: str, content: str) -> SafetyResult:
    """调用微信 msgSecCheck；未启用或失败时返回 ok=True 并由人工审核兜底。"""
    if not settings.wx_content_security_enabled:
        return SafetyResult(ok=True, reason="content_security_disabled")
    text = (content or "").strip()
    if not text:
        return SafetyResult(ok=True)
    try:
        token = await WechatService.get_access_token()
        url = f"https://api.weixin.qq.com/wxa/msg_sec_check?access_token={token}"
        payload = {
            "openid": openid,
            "scene": 3,
            "version": 2,
            "content": text[:2500],
        }
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.post(url, json=payload)
            data = resp.json()
        errcode = data.get("errcode", -1)
        if errcode == 0:
            result = (data.get("result") or {}).get("suggest") or "pass"
            if result in ("risky", "review"):
                return SafetyResult(
                    ok=result != "risky",
                    reason="微信内容安全未通过" if result == "risky" else "需人工复核",
                    hit_level="block" if result == "risky" else "review",
                )
            return SafetyResult(ok=True)
        if errcode == 87014:
            return SafetyResult(ok=False, reason="内容未通过安全检测", hit_level="block")
        logger.warning("msg_sec_check unexpected: errcode=%s", errcode)
        return SafetyResult(ok=True, reason=f"sec_check_skip:{errcode}")
    except Exception as exc:
        logger.warning("msg_sec_check failed: %s", exc.__class__.__name__)
        return SafetyResult(ok=True, reason="sec_check_error")


async def wechat_img_sec_check(*, image_bytes: bytes, filename: str = "image.jpg") -> SafetyResult:
    """调用微信 imgSecCheck（同步）；未启用时跳过。单图建议 ≤1MB。"""
    if not settings.wx_content_security_enabled:
        return SafetyResult(ok=True, reason="content_security_disabled")
    if not image_bytes:
        return SafetyResult(ok=True)
    # 接口限制约 1MB；超限仍上传但跳过机审，依赖人工审核
    if len(image_bytes) > 1_000_000:
        logger.info("img_sec_check skipped: image too large for sync api")
        return SafetyResult(ok=True, reason="img_too_large_skip")
    try:
        token = await WechatService.get_access_token()
        url = f"https://api.weixin.qq.com/wxa/img_sec_check?access_token={token}"
        files = {"media": (filename, image_bytes, "application/octet-stream")}
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, files=files)
            data = resp.json()
        errcode = data.get("errcode", -1)
        if errcode == 0:
            return SafetyResult(ok=True)
        if errcode == 87014:
            return SafetyResult(ok=False, reason="图片未通过安全检测", hit_level="block")
        logger.warning("img_sec_check unexpected: errcode=%s", errcode)
        return SafetyResult(ok=True, reason=f"img_sec_skip:{errcode}")
    except Exception as exc:
        logger.warning("img_sec_check failed: %s", exc.__class__.__name__)
        return SafetyResult(ok=True, reason="img_sec_error")


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
        return SafetyResult(ok=True, hit_level="review", reason="需人工复核")
    return SafetyResult(ok=True)
