from fastapi import HTTPException

from app.core.config import settings


def block_mock_in_production() -> None:
    if settings.app_env != "production":
        return
    if settings.pre_wechat_launch and not settings.wx_pay_configured:
        return
    raise HTTPException(status_code=404, detail="Not Found")
