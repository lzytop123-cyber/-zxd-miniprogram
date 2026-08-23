"""阿里云通用文字识别。AccessKey 仅服务端使用；未配置或失败返回空串。"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import secrets
from datetime import datetime, timezone
import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_ALGORITHM = "ACS3-HMAC-SHA256"


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _hmac_sha256(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def _canonical_headers(headers: dict[str, str]) -> tuple[str, str]:
    items = sorted((k.lower(), v.strip()) for k, v in headers.items())
    signed = ";".join(k for k, _ in items)
    canonical = "".join(f"{k}:{v}\n" for k, v in items)
    return canonical, signed


def recognize_general(image_bytes: bytes) -> str:
    ak = (settings.aliyun_access_key_id or "").strip()
    sk = (settings.aliyun_access_key_secret or "").strip()
    if not ak or not sk or not image_bytes:
        return ""

    host = (settings.aliyun_ocr_endpoint or "ocr-api.cn-hangzhou.aliyuncs.com").strip()
    host = host.replace("https://", "").replace("http://", "").rstrip("/")
    payload = image_bytes
    hashed_payload = _sha256_hex(payload)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    nonce = secrets.token_hex(16)

    sign_headers = {
        "host": host,
        "x-acs-action": "RecognizeGeneral",
        "x-acs-content-sha256": hashed_payload,
        "x-acs-date": now,
        "x-acs-signature-nonce": nonce,
        "x-acs-version": "2021-07-07",
    }
    canonical_headers, signed_headers = _canonical_headers(sign_headers)
    canonical_request = "\n".join(
        [
            "POST",
            "/",
            "",
            canonical_headers,
            signed_headers,
            hashed_payload,
        ]
    )
    string_to_sign = f"{_ALGORITHM}\n{_sha256_hex(canonical_request.encode('utf-8'))}"
    signature = hmac.new(sk.encode("utf-8"), string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()
    authorization = (
        f"{_ALGORITHM} Credential={ak},SignedHeaders={signed_headers},Signature={signature}"
    )

    headers = {
        **sign_headers,
        "Authorization": authorization,
        "Content-Type": "application/octet-stream",
        "x-acs-signature-nonce": nonce,
    }
    url = f"https://{host}/"
    try:
        with httpx.Client(timeout=12.0) as client:
            resp = client.post(url, content=payload, headers=headers)
        if resp.status_code >= 400:
            logger.warning("Aliyun OCR HTTP %s: %s", resp.status_code, resp.text[:400])
            return ""
        data = resp.json()
    except Exception as exc:
        logger.warning("Aliyun OCR failed: %s", exc.__class__.__name__)
        return ""

    raw = data.get("Data") or data.get("data") or ""
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return raw.strip()
        return str(parsed.get("content") or parsed.get("Content") or "").strip()
    if isinstance(raw, dict):
        return str(raw.get("content") or raw.get("Content") or "").strip()
    return ""
