from __future__ import annotations

import uuid
from datetime import datetime, timezone
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

    return datetime.now(timezone.utc).replace(tzinfo=None)


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
        nullable=False,
    )

    file_hash: Mapped[Optional[str]] = mapped_column(
        String(128),
        nullable=True,
        index=True,
    )

    character_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    paragraph_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    page_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    chapter_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        default="uploaded",
        nullable=False,
    )

    export_status: Mapped[str] = mapped_column(
        String(50),
        default="pending",
        nullable=False,
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
        nullable=False,
    )

    estimated_output_tokens: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    actual_input_tokens: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    actual_output_tokens: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    total_processing_seconds: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utc_now,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    chapters: Mapped[list["Chapter"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    quizzes: Mapped[list["Quiz"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    flashcards: Mapped[list["Flashcard"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    weak_points: Mapped[list["WeakPoint"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
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
        UniqueConstraint(
            "document_id",
            "source_chapter_id",
            name="uq_chapter_document_source_id",
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
        index=True,
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

    source: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    start_index: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )

    end_index: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )

    character_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    subsection_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    export_status: Mapped[str] = mapped_column(
        String(50),
        default="pending",
        nullable=False,
    )

    visual_cache_status: Mapped[str] = mapped_column(
        String(50),
        default="pending",
        nullable=False,
    )

    note_cache_status: Mapped[str] = mapped_column(
        String(50),
        default="pending",
        nullable=False,
    )

    notion_page_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )

    notion_page_url: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utc_now,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    document: Mapped["Document"] = relationship(
        back_populates="chapters",
    )

    quizzes: Mapped[list["Quiz"]] = relationship(
        back_populates="chapter",
        passive_deletes=True,
    )

    flashcards: Mapped[list["Flashcard"]] = relationship(
        back_populates="chapter",
        passive_deletes=True,
    )

    weak_points: Mapped[list["WeakPoint"]] = relationship(
        back_populates="chapter",
        passive_deletes=True,
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
        index=True,
    )

    chapter_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey(
            "chapters.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
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
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utc_now,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
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
        passive_deletes=True,
    )

    weak_points: Mapped[list["WeakPoint"]] = relationship(
        back_populates="quiz",
        cascade="all, delete-orphan",
        passive_deletes=True,
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
        index=True,
    )

    chapter_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey(
            "chapters.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
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
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
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
        passive_deletes=True,
    )


class QuizAttempt(Base):
    """Quiz 作答與自評紀錄。"""

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
        index=True,
    )

    user_answer: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    self_rating: Mapped[str] = mapped_column(
        String(20),
        default="wrong",
        nullable=False,
    )

    score: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    is_correct: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    answered_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utc_now,
        nullable=False,
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
        index=True,
    )

    familiarity_score: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    reviewed_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utc_now,
        nullable=False,
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
        index=True,
    )

    item_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        index=True,
    )

    document_id: Mapped[str] = mapped_column(
        ForeignKey(
            "documents.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    due_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
    )

    interval_days: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )

    repetition_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    ease_factor: Mapped[float] = mapped_column(
        Float,
        default=2.5,
        nullable=False,
    )

    is_completed: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utc_now,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )


class WeakPoint(Base):
    """Quiz 錯題與不熟重點紀錄。"""

    __tablename__ = "weak_points"

    __table_args__ = (
        UniqueConstraint(
            "quiz_id",
            name="uq_weak_point_quiz",
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
        index=True,
    )

    chapter_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey(
            "chapters.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    quiz_id: Mapped[str] = mapped_column(
        ForeignKey(
            "quizzes.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    title: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    source_type: Mapped[str] = mapped_column(
        String(30),
        default="quiz",
        nullable=False,
    )

    weakness_score: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    wrong_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    partial_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    correct_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    last_answer: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    correct_answer: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    explanation: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        default="active",
        nullable=False,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utc_now,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    document: Mapped["Document"] = relationship(
        back_populates="weak_points",
    )

    chapter: Mapped[Optional["Chapter"]] = relationship(
        back_populates="weak_points",
    )

    quiz: Mapped["Quiz"] = relationship(
        back_populates="weak_points",
    )
