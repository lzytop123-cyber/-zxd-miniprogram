"""后台：门店图片座位图与区域管理。"""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin
from app.core.static_url import public_static_url
from app.db.session import get_db
from app.models import AdminUser, Seat, Store, Zone
from app.schemas.common import ResponseModel
from app.services.admin_access import assert_store_access
from app.services.store_seat_maps import (
    SeatMapError,
    get_draft_map,
    get_published_map,
    is_image_mode,
    list_archived_maps,
    map_summary,
    publish_draft_map,
    restore_map,
    save_draft_map,
    zone_to_dict,
)

router = APIRouter(prefix="/admin", tags=["座位图"])

SEAT_MAP_DIR = Path(__file__).resolve().parents[3] / "uploads" / "seat-maps"
ALLOWED_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}
MAX_BYTES = 2 * 1024 * 1024


class DraftBody(BaseModel):
    image_path: str
    aspect_ratio: float = Field(..., gt=0)
    markers: list[dict] = Field(default_factory=list)


class ZoneBody(BaseModel):
    name: str
    type: str | None = "standard"
    sort_order: int = 0


class ZoneUpdateBody(BaseModel):
    name: str | None = None
    type: str | None = None
    sort_order: int | None = None


def _store(db: Session, admin: AdminUser, store_id: int) -> Store:
    assert_store_access(admin, store_id)
    store = db.get(Store, store_id)
    if not store:
        raise HTTPException(status_code=404, detail="门店不存在")
    return store


@router.get("/stores/{store_id}/seat-map", response_model=ResponseModel)
def admin_get_seat_map(
    store_id: int,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    store = _store(db, admin, store_id)
    draft = get_draft_map(db, store_id)
    published = get_published_map(db, store_id)
    archived = list_archived_maps(db, store_id)
    return ResponseModel(
        data={
            "store_id": store_id,
            "seat_map_mode": getattr(store, "seat_map_mode", "legacy") or "legacy",
            "store_status": store.status,
            "floor_plan": public_static_url(store.floor_plan) if store.floor_plan else None,
            "draft": _enrich_map(draft),
            "published": _enrich_map(published),
            "archived": [_enrich_map(a, markers=False) for a in archived],
        }
    )


def _enrich_map(row, *, markers: bool = True) -> dict | None:
    data = map_summary(row, include_markers=markers)
    if not data:
        return None
    if data.get("image_path"):
        data["image_url"] = public_static_url(data["image_path"])
    return data


@router.post("/stores/{store_id}/seat-map/image", response_model=ResponseModel)
async def admin_upload_seat_map_image(
    store_id: int,
    file: UploadFile = File(...),
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    store = _store(db, admin, store_id)
    if not is_image_mode(store):
        raise HTTPException(status_code=400, detail="该门店为固定布局，不能上传座位图")

    content_type = (file.content_type or "").lower()
    ext = ALLOWED_TYPES.get(content_type)
    if not ext:
        raise HTTPException(status_code=400, detail="仅支持 JPEG/PNG/WebP/GIF")

    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="空文件")
    if len(raw) > MAX_BYTES:
        raise HTTPException(status_code=400, detail="图片不能超过 2MB")

    SEAT_MAP_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{store_id}_{uuid.uuid4().hex}{ext}"
    dest = SEAT_MAP_DIR / filename
    dest.write_bytes(raw)
    path = f"/static/seat-maps/{filename}"
    return ResponseModel(
        data={"path": path, "url": public_static_url(path)},
        message="已上传",
    )


@router.put("/stores/{store_id}/seat-map/draft", response_model=ResponseModel)
def admin_save_seat_map_draft(
    store_id: int,
    body: DraftBody,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    _store(db, admin, store_id)
    try:
        draft = save_draft_map(
            db,
            store_id,
            image_path=body.image_path,
            aspect_ratio=body.aspect_ratio,
            markers=body.markers,
        )
        db.commit()
        db.refresh(draft)
    except SeatMapError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e)) from e
    return ResponseModel(message="草稿已保存", data=_enrich_map(draft))


@router.post("/stores/{store_id}/seat-map/publish", response_model=ResponseModel)
def admin_publish_seat_map(
    store_id: int,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    _store(db, admin, store_id)
    try:
        published = publish_draft_map(db, store_id, require_all_enabled=True)
        db.commit()
        db.refresh(published)
    except SeatMapError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e)) from e
    return ResponseModel(message="座位图已发布", data=_enrich_map(published))


@router.post("/stores/{store_id}/seat-map/restore/{map_id}", response_model=ResponseModel)
def admin_restore_seat_map(
    store_id: int,
    map_id: int,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    _store(db, admin, store_id)
    try:
        published = restore_map(db, store_id, map_id)
        db.commit()
        db.refresh(published)
    except SeatMapError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e)) from e
    return ResponseModel(message="已恢复座位图", data=_enrich_map(published))


@router.get("/stores/{store_id}/zones", response_model=ResponseModel)
def admin_list_zones(
    store_id: int,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    _store(db, admin, store_id)
    zones = db.scalars(select(Zone).where(Zone.store_id == store_id).order_by(Zone.sort_order, Zone.id)).all()
    return ResponseModel(data=[zone_to_dict(z) for z in zones])


@router.post("/stores/{store_id}/zones", response_model=ResponseModel)
def admin_create_zone(
    store_id: int,
    body: ZoneBody,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    _store(db, admin, store_id)
    name = (body.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="区域名称不能为空")
    zone = Zone(store_id=store_id, name=name, type=body.type or "standard", sort_order=body.sort_order)
    db.add(zone)
    db.commit()
    db.refresh(zone)
    return ResponseModel(message="区域已创建", data=zone_to_dict(zone))


@router.put("/stores/{store_id}/zones/{zone_id}", response_model=ResponseModel)
def admin_update_zone(
    store_id: int,
    zone_id: int,
    body: ZoneUpdateBody,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    _store(db, admin, store_id)
    zone = db.get(Zone, zone_id)
    if not zone or zone.store_id != store_id:
        raise HTTPException(status_code=404, detail="区域不存在")
    if body.name is not None:
        name = body.name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="区域名称不能为空")
        zone.name = name
    if body.type is not None:
        zone.type = body.type
    if body.sort_order is not None:
        zone.sort_order = body.sort_order
    db.commit()
    db.refresh(zone)
    return ResponseModel(message="区域已更新", data=zone_to_dict(zone))


@router.delete("/stores/{store_id}/zones/{zone_id}", response_model=ResponseModel)
def admin_delete_zone(
    store_id: int,
    zone_id: int,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    _store(db, admin, store_id)
    zone = db.get(Zone, zone_id)
    if not zone or zone.store_id != store_id:
        raise HTTPException(status_code=404, detail="区域不存在")
    seat_count = db.scalar(select(func.count()).select_from(Seat).where(Seat.zone_id == zone_id)) or 0
    if seat_count:
        raise HTTPException(status_code=400, detail="区域内仍有座位，无法删除")
    db.delete(zone)
    db.commit()
    return ResponseModel(message="区域已删除")
