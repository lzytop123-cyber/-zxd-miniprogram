from fastapi import HTTPException

from app.core.config import settings


def block_mock_in_production() -> None:
    if not settings.is_production:
        return
    raise HTTPException(status_code=404, detail="Not Found")
