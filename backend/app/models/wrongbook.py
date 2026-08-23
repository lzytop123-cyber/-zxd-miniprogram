"""错题本：学科与错题。"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class WrongbookSubject(Base):
    __tablename__ = "wrongbook_subjects"
    __table_args__ = (Index("ix_wrongbook_subjects_user", "user_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    is_preset: Mapped[int] = mapped_column(Integer, default=0)
    sort: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class WrongQuestion(Base):
    __tablename__ = "wrong_questions"
    __table_args__ = (
        Index("ix_wrong_questions_user", "user_id"),
        Index("ix_wrong_questions_user_subject", "user_id", "subject_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    subject_id: Mapped[int] = mapped_column(Integer, ForeignKey("wrongbook_subjects.id"), nullable=False)
    image_urls: Mapped[list] = mapped_column(JSON, nullable=False)
    ocr_text: Mapped[str | None] = mapped_column(Text)
    answer_text: Mapped[str | None] = mapped_column(Text)
    answer_image_urls: Mapped[list | None] = mapped_column(JSON)
    reason: Mapped[str | None] = mapped_column(String(200))
    tags: Mapped[list | None] = mapped_column(JSON)
    status: Mapped[int] = mapped_column(Integer, default=0)
    review_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
