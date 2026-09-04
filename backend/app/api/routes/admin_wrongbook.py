"""错题本管理端接口。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin
from app.db.session import get_db
from app.models import AdminUser, User
from app.models.wrongbook import WrongbookSubject, WrongQuestion
from app.schemas.common import PageResult, ResponseModel
from app.services import wrongbook as svc
from app.services.admin_audit import log_admin_action

router = APIRouter(prefix="/admin/wrongbook", tags=["后台-错题本"])


class QuestionUpdateBody(BaseModel):
    subject_id: int | None = None
    ocr_text: str | None = None
    answer_text: str | None = None
    reason: str | None = Field(default=None, max_length=200)
    tags: list[str] | None = None
    status: int | None = Field(default=None, ge=0, le=2)


def _admin_question_item(
    row: WrongQuestion,
    subject: WrongbookSubject | None,
    user: User | None,
) -> dict:
    data = svc.question_to_dict(row, subject)
    data["user_nickname"] = user.nickname if user else None
    data["user_phone"] = user.phone if user else None
    images = data.get("image_urls") or []
    data["thumb_url"] = images[0] if images else None
    return data


def _load_subject_map(db: Session, rows: list[WrongQuestion]) -> dict[int, WrongbookSubject]:
    ids = {r.subject_id for r in rows}
    if not ids:
        return {}
    subjects = db.scalars(select(WrongbookSubject).where(WrongbookSubject.id.in_(ids))).all()
    return {s.id: s for s in subjects}


def _load_user_map(db: Session, rows: list[WrongQuestion]) -> dict[int, User]:
    ids = {r.user_id for r in rows}
    if not ids:
        return {}
    users = db.scalars(select(User).where(User.id.in_(ids))).all()
    return {u.id: u for u in users}


def _get_question_or_404(db: Session, question_id: int) -> WrongQuestion:
    row = db.get(WrongQuestion, question_id)
    if not row:
        raise HTTPException(status_code=404, detail="错题不存在")
    return row


@router.get("/questions", response_model=ResponseModel)
def list_questions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user_id: int | None = None,
    subject_id: int | None = None,
    status: int | None = Query(None, ge=0, le=2),
    keyword: str | None = None,
    _: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    query = select(WrongQuestion)
    if user_id is not None:
        query = query.where(WrongQuestion.user_id == user_id)
    if subject_id is not None:
        query = query.where(WrongQuestion.subject_id == subject_id)
    if status is not None:
        query = query.where(WrongQuestion.status == status)
    if keyword and keyword.strip():
        kw = f"%{keyword.strip()}%"
        query = query.outerjoin(User, User.id == WrongQuestion.user_id).where(
            or_(
                WrongQuestion.ocr_text.like(kw),
                WrongQuestion.reason.like(kw),
                WrongQuestion.answer_text.like(kw),
                User.nickname.like(kw),
                User.phone.like(kw),
            )
        )

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = list(
        db.scalars(
            query.order_by(WrongQuestion.updated_at.desc(), WrongQuestion.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
    )
    subjects = _load_subject_map(db, rows)
    users = _load_user_map(db, rows)
    items = [
        _admin_question_item(row, subjects.get(row.subject_id), users.get(row.user_id))
        for row in rows
    ]
    return ResponseModel(
        data=PageResult(items=items, total=total, page=page, page_size=page_size)
    )


@router.get("/questions/{question_id}", response_model=ResponseModel)
def get_question(
    question_id: int,
    _: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    row = _get_question_or_404(db, question_id)
    subject = db.get(WrongbookSubject, row.subject_id)
    user = db.get(User, row.user_id)
    return ResponseModel(data=_admin_question_item(row, subject, user))


@router.put("/questions/{question_id}", response_model=ResponseModel)
def update_question(
    question_id: int,
    body: QuestionUpdateBody,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    row = _get_question_or_404(db, question_id)
    if body.subject_id is not None:
        subject = db.get(WrongbookSubject, body.subject_id)
        if not subject or subject.user_id != row.user_id:
            raise HTTPException(status_code=400, detail="学科不存在或不属于该用户")
        row.subject_id = body.subject_id
    if body.ocr_text is not None:
        row.ocr_text = body.ocr_text
    if body.answer_text is not None:
        row.answer_text = body.answer_text
    if body.reason is not None:
        row.reason = body.reason
    if body.tags is not None:
        row.tags = [str(t).strip() for t in body.tags if str(t).strip()]
    if body.status is not None:
        row.status = body.status

    log_admin_action(
        db,
        admin,
        "wrongbook_update",
        target_type="wrong_question",
        target_id=question_id,
    )
    db.commit()
    db.refresh(row)
    subject = db.get(WrongbookSubject, row.subject_id)
    user = db.get(User, row.user_id)
    return ResponseModel(data=_admin_question_item(row, subject, user))


@router.delete("/questions/{question_id}", response_model=ResponseModel)
def delete_question(
    question_id: int,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    row = _get_question_or_404(db, question_id)
    db.delete(row)
    log_admin_action(
        db,
        admin,
        "wrongbook_delete",
        target_type="wrong_question",
        target_id=question_id,
    )
    db.commit()
    return ResponseModel(message="已删除")


@router.get("/subjects", response_model=ResponseModel)
def list_subjects(
    user_id: int = Query(..., ge=1),
    _: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    rows = db.scalars(
        select(WrongbookSubject)
        .where(WrongbookSubject.user_id == user_id)
        .order_by(WrongbookSubject.sort, WrongbookSubject.id)
    ).all()
    return ResponseModel(data=[svc.subject_to_dict(r) for r in rows])
