from app.core.config import settings

_STATIC_MARKER = "/static/"


def public_static_path(url: str | None) -> str:
    """Return /static/... path only (for miniprogram client-side host resolution)."""
    if not url:
        return ""
    value = url.strip()
    if not value:
        return ""
    if value.startswith("/static/"):
        return value
    if _STATIC_MARKER in value:
        return value[value.index(_STATIC_MARKER) :]
    return value


def public_static_url(url: str | None) -> str:
    """Return a full URL for admin / server-side use."""
    path = public_static_path(url)
    if not path.startswith("/static/"):
        return path
    return f"{settings.base_url.rstrip('/')}{path}"
