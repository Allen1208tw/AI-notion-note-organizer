from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.database import Base


def create_uuid() -> str:
    """建立 UUID 字串。"""

    return str(uuid.uuid4())


def utc_now() -> datetime:
    """取得目前 UTC 時間。"""

    return datetime.utcnow()


class Document(Base):
    """上傳文件紀錄。"""

    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=create_uuid,
    )

    file_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    file_extension: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    file_size_bytes: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    file_hash: Mapped[Optional[str]] = mapped_column(
        String(128),
        nullable=True,
    )

    character_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    page_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    chapter_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        default="uploaded",
    )

    notion_parent_page_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )

    notion_parent_url: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    estimated_input_tokens: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    estimated_output_tokens: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    actual_input_tokens: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    actual_output_tokens: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    total_processing_seconds: Mapped[float] = mapped_column(
        Float,
        default=0.0,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utc_now,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utc_now,
        onupdate=utc_now,
    )

    chapters: Mapped[list["Chapter"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
    )

    quizzes: Mapped[list["Quiz"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
    )

    flashcards: Mapped[list["Flashcard"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
    )


class Chapter(Base):
    """文件中的 Module / 主章節紀錄。"""

    __tablename__ = "chapters"

    __table_args__ = (
        UniqueConstraint(
            "document_id",
            "chapter_order",
            name="uq_chapter_document_order",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=create_uuid,
    )

    document_id: Mapped[str] = mapped_column(
        ForeignKey(
            "documents.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    source_chapter_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    chapter_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    title: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )

    character_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    export_status: Mapped[str] = mapped_column(
        String(50),
        default="pending",
    )

    visual_cache_status: Mapped[str] = mapped_column(
        String(50),
        default="pending",
    )

    note_cache_status: Mapped[str] = mapped_column(
        String(50),
        default="pending",
    )

    notion_page_url: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utc_now,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utc_now,
        onupdate=utc_now,
    )

    document: Mapped["Document"] = relationship(
        back_populates="chapters",
    )

    quizzes: Mapped[list["Quiz"]] = relationship(
        back_populates="chapter",
        cascade="all, delete-orphan",
    )

    flashcards: Mapped[list["Flashcard"]] = relationship(
        back_populates="chapter",
        cascade="all, delete-orphan",
    )


class Quiz(Base):
    """AI 生成的 Quiz 題目。"""

    __tablename__ = "quizzes"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=create_uuid,
    )

    document_id: Mapped[str] = mapped_column(
        ForeignKey(
            "documents.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    chapter_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey(
            "chapters.id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )

    question: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    correct_answer: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    explanation: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    difficulty: Mapped[str] = mapped_column(
        String(30),
        default="medium",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utc_now,
    )

    document: Mapped["Document"] = relationship(
        back_populates="quizzes",
    )

    chapter: Mapped[Optional["Chapter"]] = relationship(
        back_populates="quizzes",
    )

    attempts: Mapped[list["QuizAttempt"]] = relationship(
        back_populates="quiz",
        cascade="all, delete-orphan",
    )


class Flashcard(Base):
    """AI 生成的 Flash Card。"""

    __tablename__ = "flashcards"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=create_uuid,
    )

    document_id: Mapped[str] = mapped_column(
        ForeignKey(
            "documents.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    chapter_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey(
            "chapters.id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )

    front: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    back: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utc_now,
    )

    document: Mapped["Document"] = relationship(
        back_populates="flashcards",
    )

    chapter: Mapped[Optional["Chapter"]] = relationship(
        back_populates="flashcards",
    )

    reviews: Mapped[list["FlashcardReview"]] = relationship(
        back_populates="flashcard",
        cascade="all, delete-orphan",
    )


class QuizAttempt(Base):
    """Quiz 作答紀錄。"""

    __tablename__ = "quiz_attempts"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=create_uuid,
    )

    quiz_id: Mapped[str] = mapped_column(
        ForeignKey(
            "quizzes.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    user_answer: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    is_correct: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    answered_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utc_now,
    )

    quiz: Mapped["Quiz"] = relationship(
        back_populates="attempts",
    )


class FlashcardReview(Base):
    """Flash Card 複習紀錄。"""

    __tablename__ = "flashcard_reviews"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=create_uuid,
    )

    flashcard_id: Mapped[str] = mapped_column(
        ForeignKey(
            "flashcards.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    familiarity_score: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    reviewed_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utc_now,
    )

    flashcard: Mapped["Flashcard"] = relationship(
        back_populates="reviews",
    )


class ReviewSchedule(Base):
    """複習排程紀錄。"""

    __tablename__ = "review_schedules"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=create_uuid,
    )

    item_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    item_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
    )

    document_id: Mapped[str] = mapped_column(
        ForeignKey(
            "documents.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    due_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
    )

    interval_days: Mapped[int] = mapped_column(
        Integer,
        default=1,
    )

    repetition_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    ease_factor: Mapped[float] = mapped_column(
        Float,
        default=2.5,
    )

    is_completed: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utc_now,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utc_now,
        onupdate=utc_now,
    )