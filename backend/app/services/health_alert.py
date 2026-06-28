"""健康检查告警（Webhook）。"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from urllib import error, request

from sqlalchemy.orm import Session

from app.core.config import settings
from app.services.health import run_health_checks

logger = logging.getLogger(__name__)

_last_alert_at: datetime | None = None
ALERT_COOLDOWN = timedelta(hours=1)


def maybe_send_health_alert(db: Session) -> dict:
    global _last_alert_at
    webhook = (settings.health_alert_webhook or "").strip()
    if not webhook:
        return {"sent": False, "reason": "webhook_not_configured"}

    result = run_health_checks(db)
    if result.get("status") == "ok":
        return {"sent": False, "reason": "healthy", "checks": result.get("checks")}

    now = datetime.now(timezone.utc)
    if _last_alert_at and now - _last_alert_at < ALERT_COOLDOWN:
        return {"sent": False, "reason": "cooldown", "status": result.get("status")}

    payload = {
        "text": f"[知行岛] 健康检查异常: status={result.get('status')}, checks={result.get('checks')}",
        "status": result.get("status"),
        "checks": result.get("checks"),
        "timestamp": result.get("timestamp"),
        "base_url": settings.base_url,
    }
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = request.Request(
        webhook,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=10) as resp:
            _last_alert_at = now
            return {"sent": True, "status_code": resp.status, "health": result}
    except error.URLError as exc:
        logger.warning("health alert webhook failed: %s", exc)
        return {"sent": False, "reason": str(exc), "health": result}
