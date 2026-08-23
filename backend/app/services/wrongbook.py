"""错题本：学科播种、序列化、按用户隔离。"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.wrongbook import WrongbookSubject, WrongQuestion

PRESET_SUBJECTS = ("政治", "英语", "数学", "行测", "申论", "专业课", "其他")

STATUS_LABELS = {0: "未掌握", 1: "仍然错", 2: "已掌握"}


def ensure_preset_subjects(db: Session, user_id: int) -> list[WrongbookSubject]:
    rows = db.scalars(
        select(WrongbookSubject).where(WrongbookSubject.user_id == user_id).order_by(
            WrongbookSubject.sort, WrongbookSubject.id
        )
    ).all()
    if rows:
        return list(rows)
    created: list[WrongbookSubject] = []
    for i, name in enumerate(PRESET_SUBJECTS):
        item = WrongbookSubject(user_id=user_id, name=name, is_preset=1, sort=i)
        db.add(item)
        created.append(item)
    db.commit()
    for item in created:
        db.refresh(item)
    return created


def subject_to_dict(row: WrongbookSubject) -> dict:
    return {
        "id": row.id,
        "user_id": row.user_id,
        "name": row.name,
        "is_preset": bool(row.is_preset),
        "sort": row.sort,
    }


def question_to_dict(row: WrongQuestion, subject: WrongbookSubject | None = None) -> dict:
    return {
        "id": row.id,
        "user_id": row.user_id,
        "subject_id": row.subject_id,
        "subject_name": subject.name if subject else None,
        "image_urls": row.image_urls or [],
        "ocr_text": row.ocr_text or "",
        "answer_text": row.answer_text or "",
        "answer_image_urls": row.answer_image_urls or [],
        "reason": row.reason or "",
        "tags": row.tags or [],
        "status": row.status,
        "status_label": STATUS_LABELS.get(row.status, "未掌握"),
        "review_count": row.review_count or 0,
        "created_at": row.created_at.isoformat(sep=" ", timespec="seconds") if row.created_at else None,
        "updated_at": row.updated_at.isoformat(sep=" ", timespec="seconds") if row.updated_at else None,
    }


def collect_user_tags(db: Session, user_id: int) -> list[str]:
    rows = db.scalars(
        select(WrongQuestion.tags).where(WrongQuestion.user_id == user_id, WrongQuestion.tags.is_not(None))
    ).all()
    seen: list[str] = []
    for tags in rows:
        if not isinstance(tags, list):
            continue
        for tag in tags:
            name = str(tag).strip()
            if name and name not in seen:
                seen.append(name)
    return seen


def count_questions_in_subject(db: Session, user_id: int, subject_id: int) -> int:
    return (
        db.scalar(
            select(func.count())
            .select_from(WrongQuestion)
            .where(WrongQuestion.user_id == user_id, WrongQuestion.subject_id == subject_id)
        )
        or 0
    )
