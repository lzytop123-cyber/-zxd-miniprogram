"""阿里云通用文字识别。AccessKey 仅服务端使用；未配置或失败返回空串。"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import uuid
from datetime import datetime, timezone

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_ALGORITHM = "ACS3-HMAC-SHA256"


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def recognize_general(image_bytes: bytes) -> tuple[str, str]:
    """返回 (识别文本, 失败原因)。成功时原因为空串。"""
    ak = (settings.aliyun_access_key_id or "").strip()
    sk = (settings.aliyun_access_key_secret or "").strip()
    if not ak or not sk:
        return "", "未配置阿里云 OCR 密钥"
    if not image_bytes:
        return "", "图片为空"

    host = (settings.aliyun_ocr_endpoint or "ocr-api.cn-hangzhou.aliyuncs.com").strip()
    host = host.replace("https://", "").replace("http://", "").rstrip("/")
    hashed_payload = _sha256_hex(image_bytes)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    headers = {
        "content-type": "application/octet-stream",
        "host": host,
        "x-acs-action": "RecognizeGeneral",
        "x-acs-content-sha256": hashed_payload,
        "x-acs-date": now,
        "x-acs-signature-nonce": str(uuid.uuid4()),
        "x-acs-version": "2021-07-07",
    }
    signed_items = sorted((k, v) for k, v in headers.items())
    signed_headers = ";".join(k for k, _ in signed_items)
    canonical_headers = "".join(f"{k}:{v}\n" for k, v in signed_items)
    canonical_request = "\n".join(
        ["POST", "/", "", canonical_headers, signed_headers, hashed_payload]
    )
    string_to_sign = f"{_ALGORITHM}\n{_sha256_hex(canonical_request.encode('utf-8'))}"
    signature = hmac.new(sk.encode("utf-8"), string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()
    headers["Authorization"] = (
        f"{_ALGORITHM} Credential={ak},SignedHeaders={signed_headers},Signature={signature}"
    )

    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(f"https://{host}/", content=image_bytes, headers=headers)
        data = resp.json() if resp.content else {}
    except Exception as exc:
        logger.warning("Aliyun OCR failed: %s", exc.__class__.__name__)
        return "", "识别服务暂时不可用"

    code = str(data.get("Code") or data.get("code") or "").strip()
    message = str(data.get("Message") or data.get("message") or "").strip()
    if resp.status_code >= 400 or code:
        logger.warning("Aliyun OCR error HTTP %s code=%s msg=%s", resp.status_code, code, message[:200])
        return "", message or code or f"识别失败({resp.status_code})"

    raw = data.get("Data") or data.get("data") or ""
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return raw.strip(), ""
        text = str(parsed.get("content") or parsed.get("Content") or "").strip()
        return text, "" if text else "未识别到文字"
    if isinstance(raw, dict):
        text = str(raw.get("content") or raw.get("Content") or "").strip()
        return text, "" if text else "未识别到文字"
    return "", "未识别到文字"
