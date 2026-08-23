"""错题本 C 端接口。"""

from __future__ import annotations

import time
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.redis_client import get_redis
from app.db.session import get_db
from app.models import User
from app.models.wrongbook import WrongbookSubject, WrongQuestion
from app.schemas.common import PageResult, ResponseModel
from app.services import aliyun_ocr
from app.services import wrongbook as svc

router = APIRouter(prefix="/wrongbook", tags=["错题本"])

UPLOAD_DIR = Path(__file__).resolve().parents[3] / "uploads" / "wrongbook"
IMAGE_TYPES = {
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}
MAX_IMAGE_BYTES = 5 * 1024 * 1024
UPLOAD_PER_MINUTE = 8


class QuestionCreateBody(BaseModel):
    subject_id: int
    image_urls: list[str] = Field(min_length=1)
    ocr_text: str = ""
    answer_text: str = ""
    answer_image_urls: list[str] = Field(default_factory=list)
    reason: str = ""
    tags: list[str] = Field(default_factory=list)


class QuestionUpdateBody(BaseModel):
    subject_id: int | None = None
    image_urls: list[str] | None = None
    ocr_text: str | None = None
    answer_text: str | None = None
    answer_image_urls: list[str] | None = None
    reason: str | None = None
    tags: list[str] | None = None
    status: int | None = None
    bump_review: bool = False


class SubjectCreateBody(BaseModel):
    name: str


def _enforce_upload_limit(user_id: int) -> None:
    client = get_redis()
    key = f"wb_up:m:{user_id}:{int(time.time() // 60)}"
    try:
        count = int(client.get(key) or 0)
    except Exception:
        return
    if count >= UPLOAD_PER_MINUTE:
        raise HTTPException(status_code=429, detail="上传太频繁，请稍后再试")
    try:
        client.set(key, str(count + 1), ex=60)
    except Exception:
        pass


def _get_owned_question(db: Session, user_id: int, question_id: int) -> WrongQuestion:
    row = db.get(WrongQuestion, question_id)
    if not row or row.user_id != user_id:
        raise HTTPException(status_code=404, detail="错题不存在")
    return row


def _get_owned_subject(db: Session, user_id: int, subject_id: int) -> WrongbookSubject:
    row = db.get(WrongbookSubject, subject_id)
    if not row or row.user_id != user_id:
        raise HTTPException(status_code=404, detail="学科不存在")
    return row


def _normalize_tags(tags: list[str] | None) -> list[str]:
    seen: list[str] = []
    for tag in tags or []:
        name = str(tag).strip()[:20]
        if name and name not in seen:
            seen.append(name)
    return seen[:20]


@router.post("/upload", response_model=ResponseModel)
async def upload_image(
    file: UploadFile = File(...),
    type: str = Form("question"),
    user: User = Depends(get_current_user),
):
    _enforce_upload_limit(user.id)
    upload_type = (type or "question").strip().lower()
    if upload_type not in ("question", "answer"):
        raise HTTPException(status_code=400, detail="type 须为 question 或 answer")
    content_type = (file.content_type or "").lower()
    ext = IMAGE_TYPES.get(content_type)
    if not ext:
        name = (file.filename or "").lower()
        if name.endswith(".png"):
            ext = "png"
        elif name.endswith(".webp"):
            ext = "webp"
        elif name.endswith(".jpg") or name.endswith(".jpeg"):
            ext = "jpg"
    if not ext:
        raise HTTPException(status_code=400, detail="仅支持 jpg / png / webp")
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="图片为空")
    if len(content) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=400, detail="图片不能超过 5MB")

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4().hex}.{ext}"
    (UPLOAD_DIR / filename).write_bytes(content)
    url = f"/static/wrongbook/{filename}"
    ocr_text = ""
    if upload_type == "question":
        ocr_text = aliyun_ocr.recognize_general(content)
    return ResponseModel(data={"url": url, "ocr_text": ocr_text})


@router.get("/list", response_model=ResponseModel)
def list_questions(
    subject_id: int | None = None,
    tag: str | None = None,
    status: int | None = Query(None, ge=0, le=2),
    keyword: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = select(WrongQuestion).where(WrongQuestion.user_id == user.id)
    if subject_id is not None:
        query = query.where(WrongQuestion.subject_id == subject_id)
    if status is not None:
        query = query.where(WrongQuestion.status == status)
    if keyword and keyword.strip():
        kw = f"%{keyword.strip()}%"
        query = query.where(
            or_(WrongQuestion.ocr_text.like(kw), WrongQuestion.reason.like(kw), WrongQuestion.answer_text.like(kw))
        )
    rows = db.scalars(query.order_by(WrongQuestion.updated_at.desc(), WrongQuestion.id.desc())).all()
    if tag and tag.strip():
        needle = tag.strip()
        rows = [r for r in rows if needle in (r.tags or [])]
    total = len(rows)
    start = (page - 1) * page_size
    page_rows = rows[start : start + page_size]
    subject_ids = {r.subject_id for r in page_rows}
    subjects = {}
    if subject_ids:
        for s in db.scalars(select(WrongbookSubject).where(WrongbookSubject.id.in_(subject_ids))).all():
            subjects[s.id] = s
    items = [svc.question_to_dict(r, subjects.get(r.subject_id)) for r in page_rows]
    return ResponseModel(data=PageResult(items=items, total=total, page=page, page_size=page_size))


@router.get("/subjects", response_model=ResponseModel)
def list_subjects(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = svc.ensure_preset_subjects(db, user.id)
    return ResponseModel(data=[svc.subject_to_dict(r) for r in rows])


@router.post("/subjects", response_model=ResponseModel)
def create_subject(
    body: SubjectCreateBody,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    name = (body.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="请填写学科名称")
    if len(name) > 20:
        raise HTTPException(status_code=400, detail="学科名称最多 20 字")
    svc.ensure_preset_subjects(db, user.id)
    exists = db.scalar(
        select(WrongbookSubject).where(WrongbookSubject.user_id == user.id, WrongbookSubject.name == name)
    )
    if exists:
        raise HTTPException(status_code=400, detail="该学科已存在")
    max_sort = db.scalar(select(func.max(WrongbookSubject.sort)).where(WrongbookSubject.user_id == user.id)) or 0
    row = WrongbookSubject(user_id=user.id, name=name, is_preset=0, sort=max_sort + 1)
    db.add(row)
    db.commit()
    db.refresh(row)
    return ResponseModel(data=svc.subject_to_dict(row))


@router.delete("/subjects/{subject_id}", response_model=ResponseModel)
def delete_subject(
    subject_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = _get_owned_subject(db, user.id, subject_id)
    if svc.count_questions_in_subject(db, user.id, subject_id) > 0:
        raise HTTPException(status_code=400, detail="请先移动或删除该学科下的错题")
    db.delete(row)
    db.commit()
    return ResponseModel(message="已删除")


@router.get("/tags", response_model=ResponseModel)
def list_tags(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return ResponseModel(data=svc.collect_user_tags(db, user.id))


@router.get("/{question_id}", response_model=ResponseModel)
def get_question(
    question_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = _get_owned_question(db, user.id, question_id)
    subject = db.get(WrongbookSubject, row.subject_id)
    return ResponseModel(data=svc.question_to_dict(row, subject))


@router.post("", response_model=ResponseModel)
def create_question(
    body: QuestionCreateBody,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _get_owned_subject(db, user.id, body.subject_id)
    images = [u.strip() for u in body.image_urls if u and u.strip()]
    if not images:
        raise HTTPException(status_code=400, detail="请至少上传一张题目原图")
    row = WrongQuestion(
        user_id=user.id,
        subject_id=body.subject_id,
        image_urls=images,
        ocr_text=(body.ocr_text or "").strip(),
        answer_text=(body.answer_text or "").strip(),
        answer_image_urls=[u.strip() for u in body.answer_image_urls if u and u.strip()],
        reason=(body.reason or "").strip()[:200],
        tags=_normalize_tags(body.tags),
        status=0,
        review_count=0,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    subject = db.get(WrongbookSubject, row.subject_id)
    return ResponseModel(message="已保存", data=svc.question_to_dict(row, subject))


@router.put("/{question_id}", response_model=ResponseModel)
def update_question(
    question_id: int,
    body: QuestionUpdateBody,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = _get_owned_question(db, user.id, question_id)
    if body.subject_id is not None:
        _get_owned_subject(db, user.id, body.subject_id)
        row.subject_id = body.subject_id
    if body.image_urls is not None:
        images = [u.strip() for u in body.image_urls if u and u.strip()]
        if not images:
            raise HTTPException(status_code=400, detail="请至少保留一张题目原图")
        row.image_urls = images
    if body.ocr_text is not None:
        row.ocr_text = body.ocr_text.strip()
    if body.answer_text is not None:
        row.answer_text = body.answer_text.strip()
    if body.answer_image_urls is not None:
        row.answer_image_urls = [u.strip() for u in body.answer_image_urls if u and u.strip()]
    if body.reason is not None:
        row.reason = body.reason.strip()[:200]
    if body.tags is not None:
        row.tags = _normalize_tags(body.tags)
    if body.status is not None:
        if body.status not in (0, 1, 2):
            raise HTTPException(status_code=400, detail="掌握状态无效")
        row.status = body.status
    if body.bump_review:
        row.review_count = (row.review_count or 0) + 1
    row.updated_at = datetime_now()
    db.commit()
    db.refresh(row)
    subject = db.get(WrongbookSubject, row.subject_id)
    return ResponseModel(message="已更新", data=svc.question_to_dict(row, subject))


@router.delete("/{question_id}", response_model=ResponseModel)
def delete_question(
    question_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = _get_owned_question(db, user.id, question_id)
    db.delete(row)
    db.commit()
    return ResponseModel(message="已删除")


def datetime_now():
    from datetime import datetime

    return datetime.now()
