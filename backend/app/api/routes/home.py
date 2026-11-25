from datetime import date, datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_optional_user
from app.api.routes.store import _store_list_item
from app.api.routes.user import _to_profile
from app.core.config import settings
from app.core.redis_client import cache_delete, cache_get, cache_set
from app.db.session import get_db
from app.core.static_url import public_static_url
from app.models import HomeBanner, HomeCarouselSetting, PeriodCard, SiteContactSetting, Store, SystemAnnouncement, User
from app.schemas.common import ResponseModel
from app.services.business import calc_distance
from app.services.card_service import is_period_card_active

router = APIRouter(prefix="/home", tags=["首页"])

HOME_CACHE_TTL = 60
CACHE_KEY_BANNERS = "cache:home:banners"
CACHE_KEY_CAROUSEL = "cache:home:carousel"
CACHE_KEY_ANNOUNCEMENTS = "cache:home:announcements"


def invalidate_home_cache() -> None:
    cache_delete(CACHE_KEY_BANNERS)
    cache_delete(CACHE_KEY_CAROUSEL)
    cache_delete(CACHE_KEY_ANNOUNCEMENTS)

EMPTY_BANNER = {
    "id": 0,
    "ribbon": "",
    "title_line1": "",
    "title_line2": "",
    "date_label": "",
    "date_range": "",
    "cta_text": "",
    "layout_type": "text",
    "image_url": "",
    "link_path": "",
}

DEFAULT_CAROUSEL = {
    "autoplay": True,
    "interval": 5000,
    "circular": True,
    "indicator_dots": True,
    "hero_height": 680,
    "hero_mode": "fullscreen",
    "share_title": "",
    "share_image_url": "",
}


def _banner_field(value: str | None) -> str:
    return (value or "").strip()


def _banner_from_row(row: HomeBanner) -> dict:
    return {
        "id": row.id,
        "ribbon": _banner_field(row.ribbon),
        "title_line1": _banner_field(row.title_line1),
        "title_line2": _banner_field(row.title_line2),
        "date_label": _banner_field(row.date_label),
        "date_range": _banner_field(row.date_range),
        "cta_text": _banner_field(row.cta_text),
        "layout_type": _banner_field(row.layout_type) or "text",
        "image_url": public_static_url(row.image_url),
        "link_path": _banner_field(row.link_path),
    }


def _banner_visible(data: dict) -> bool:
    layout = data.get("layout_type") or "text"
    if layout in ("image", "image_text"):
        return bool(data.get("image_url"))
    return any(
        data.get(key)
        for key in ("ribbon", "title_line1", "title_line2", "date_label", "date_range", "cta_text")
    )


def _carousel_from_row(row: HomeCarouselSetting | None) -> dict:
    if not row:
        return DEFAULT_CAROUSEL.copy()
    raw_share_img = _banner_field(getattr(row, "share_image_url", None))
    return {
        "autoplay": bool(row.autoplay),
        "interval": max(2000, row.interval or 5000),
        "circular": bool(row.circular),
        "indicator_dots": bool(row.indicator_dots),
        "hero_height": max(360, min(row.hero_height or 680, 880)),
        "hero_mode": (row.hero_mode or "fullscreen").strip() or "fullscreen",
        "share_title": _banner_field(getattr(row, "share_title", None)),
        "share_image_url": public_static_url(raw_share_img) if raw_share_img else "",
    }


def _get_carousel_settings(db: Session) -> dict:
    cached = cache_get(CACHE_KEY_CAROUSEL)
    if isinstance(cached, dict):
        return cached
    row = db.get(HomeCarouselSetting, 1)
    data = _carousel_from_row(row)
    cache_set(CACHE_KEY_CAROUSEL, data, HOME_CACHE_TTL)
    return data


def _list_active_banners(db: Session) -> list[dict]:
    cached = cache_get(CACHE_KEY_BANNERS)
    if isinstance(cached, list):
        return cached
    rows = db.scalars(
        select(HomeBanner)
        .where(HomeBanner.is_active == 1)
        .order_by(HomeBanner.sort_order, HomeBanner.id.desc())
    ).all()
    items = []
    for row in rows:
        data = _banner_from_row(row)
        if _banner_visible(data):
            items.append(data)
    cache_set(CACHE_KEY_BANNERS, items, HOME_CACHE_TTL)
    return items


@router.get("/banners", response_model=ResponseModel)
def get_home_banners(db: Session = Depends(get_db)):
    return ResponseModel(
        data={
            "items": _list_active_banners(db),
            "carousel": _get_carousel_settings(db),
        }
    )


@router.get("/banner", response_model=ResponseModel)
def get_home_banner(db: Session = Depends(get_db)):
    items = _list_active_banners(db)
    if not items:
        return ResponseModel(data=EMPTY_BANNER)
    return ResponseModel(data=items[0])


def _list_active_announcements(db: Session) -> list[dict]:
    cached = cache_get(CACHE_KEY_ANNOUNCEMENTS)
    if isinstance(cached, list):
        return cached
    now = datetime.now()
    rows = db.scalars(
        select(SystemAnnouncement)
        .where(
            SystemAnnouncement.is_active == 1,
            SystemAnnouncement.show_on_home == 1,
            or_(SystemAnnouncement.start_at.is_(None), SystemAnnouncement.start_at <= now),
            or_(SystemAnnouncement.end_at.is_(None), SystemAnnouncement.end_at >= now),
        )
        .order_by(SystemAnnouncement.priority.desc(), SystemAnnouncement.id.desc())
    ).all()
    items = [
        {
            "id": row.id,
            "title": row.title,
            "content": row.content,
            "link_path": (row.link_path or "").strip(),
            "popup_once": bool(row.popup_once),
        }
        for row in rows
    ]
    cache_set(CACHE_KEY_ANNOUNCEMENTS, items, HOME_CACHE_TTL)
    return items


@router.get("/announcements", response_model=ResponseModel)
def get_home_announcements(db: Session = Depends(get_db)):
    return ResponseModel(data={"items": _list_active_announcements(db)})


def _list_stores(db: Session, latitude: float | None, longitude: float | None) -> list:
    stores = db.scalars(select(Store).where(Store.status == 1)).all()
    items = []
    for store in stores:
        distance = None
        if latitude is not None and longitude is not None and store.latitude and store.longitude:
            distance = calc_distance(
                latitude, longitude, float(store.latitude), float(store.longitude)
            )
        items.append(_store_list_item(store, distance=distance).model_dump())
    if latitude is not None and longitude is not None:
        items.sort(key=lambda x: x.get("distance") if x.get("distance") is not None else 99999)
    return items


def _active_card_count(db: Session, user: User) -> int:
    today = date.today()
    cards = db.scalars(
        select(PeriodCard).where(PeriodCard.user_id == user.id, PeriodCard.status == 1)
    ).all()
    return sum(1 for c in cards if is_period_card_active(c, today))


@router.get("/bootstrap", response_model=ResponseModel)
def get_home_bootstrap(
    latitude: float | None = Query(None),
    longitude: float | None = Query(None),
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
):
    profile = _to_profile(db, user).model_dump() if user else None
    return ResponseModel(
        data={
            "banners": {
                "items": _list_active_banners(db),
                "carousel": _get_carousel_settings(db),
            },
            "announcements": {"items": _list_active_announcements(db)},
            "stores": _list_stores(db, latitude, longitude),
            "user": profile,
            "card_count": _active_card_count(db, user) if user else 0,
            "features": {
                "study_assistant": settings.feature_study_assistant,
                "marketplace": settings.feature_marketplace,
            },
        }
    )


@router.get("/contact", response_model=ResponseModel)
def get_home_contact(store_id: int | None = None, db: Session = Depends(get_db)):
    """小程序「联系店长」海报配置。"""
    from app.models import StoreContactSetting
    row = db.get(StoreContactSetting, store_id) if store_id else db.get(SiteContactSetting, 1)
    poster = public_static_url(row.poster_url) if row and row.poster_url else ""
    return ResponseModel(
        data={
            "poster_url": poster or None,
            "title": (row.title if row and row.title else None) or "联系店长",
            "hint": (row.hint if row and row.hint else None) or "长按识别二维码，添加店长微信咨询",
        }
    )
