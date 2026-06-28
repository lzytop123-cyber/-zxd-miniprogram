"""服务健康检查。"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings

logger = logging.getLogger(__name__)


def run_health_checks(db: Session) -> dict:
    checks: dict[str, str] = {"api": "ok"}
    status = "ok"

    try:
        db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:
        checks["database"] = f"error: {exc.__class__.__name__}"
        status = "degraded"
        logger.error("health check database failed: %s", exc)

    if settings.wx_login_configured:
        checks["wechat_login"] = "configured"
    else:
        checks["wechat_login"] = "missing"
        if status == "ok":
            status = "degraded"

    if settings.wx_pay_configured:
        checks["wechat_pay"] = "configured"
    else:
        checks["wechat_pay"] = "missing"

    return {
        "status": status,
        "checks": checks,
        "version": "1.0.2",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
