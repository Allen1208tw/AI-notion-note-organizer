from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from src.database.database import get_database_session
from src.database.models import (
    Chapter,
    Document,
    Flashcard,
    FlashcardReview,
    ReviewSchedule,
)


VALID_FAMILIARITY_SCORES = {0, 1, 2, 3, 4, 5}

FAMILIARITY_LABELS = {
    0: "完全不熟",
    1: "很不熟",
    2: "有點不熟",
    3: "普通",
    4: "熟悉",
    5: "非常熟悉",
}


def _utc_now() -> datetime:
    """取得目前 UTC 時間。"""

    return datetime.utcnow()


def _safe_text(value, default: str = "") -> str:
    """安全轉換為字串。"""

    if value is None:
        return default

    try:
        return str(value)
    except Exception:
        return default


def _safe_int(value, default: int = 0) -> int:
    """安全轉換為整數。"""

    try:
        if value is None:
            return default

        return int(value)
    except (TypeError, ValueError):
        return default


def _normalize_familiarity_score(score: int | str) -> int:
    """驗證熟悉度分數。"""

    normalized = _safe_int(
        score,
        -1,
    )

    if normalized not in VALID_FAMILIARITY_SCORES:
        raise ValueError(
            "familiarity_score 必須介於 0 到 5。"
        )

    return normalized


def _calculate_next_schedule(
    familiarity_score: int,
    previous_schedule: Optional[ReviewSchedule],
) -> dict:
    """
    依熟悉度更新簡化版 SM-2 複習排程。

    familiarity_score：
    0～2：未掌握，短期再次複習
    3：普通，維持或小幅延長
    4～5：熟悉，逐步拉長間隔
    """

    now = _utc_now()

    if previous_schedule is None:
        interval_days = 1
        repetition_count = 0
        ease_factor = 2.5
    else:
        interval_days = max(
            _safe_int(
                previous_schedule.interval_days,
                1,
            ),
            1,
        )

        repetition_count = max(
            _safe_int(
                previous_schedule.repetition_count,
                0,
            ),
            0,
        )

        try:
            ease_factor = float(
                previous_schedule.ease_factor
                or 2.5
            )
        except (TypeError, ValueError):
            ease_factor = 2.5

    if familiarity_score <= 1:
        interval_days = 1
        repetition_count = 0
        ease_factor = max(
            ease_factor - 0.20,
            1.30,
        )

    elif familiarity_score == 2:
        interval_days = 2
        repetition_count = 0
        ease_factor = max(
            ease_factor - 0.10,
            1.30,
        )

    elif familiarity_score == 3:
        repetition_count += 1
        interval_days = max(
            interval_days,
            3,
        )
        ease_factor = max(
            ease_factor - 0.05,
            1.30,
        )

    elif familiarity_score == 4:
        repetition_count += 1

        if repetition_count == 1:
            interval_days = 3
        elif repetition_count == 2:
            interval_days = 7
        else:
            interval_days = max(
                round(
                    interval_days
                    * ease_factor
                ),
                interval_days + 1,
            )

        ease_factor = min(
            ease_factor + 0.05,
            3.00,
        )

    else:
        repetition_count += 1

        if repetition_count == 1:
            interval_days = 4
        elif repetition_count == 2:
            interval_days = 10
        else:
            interval_days = max(
                round(
                    interval_days
                    * (
                        ease_factor + 0.20
                    )
                ),
                interval_days + 2,
            )

        ease_factor = min(
            ease_factor + 0.10,
            3.00,
        )

    due_at = now + timedelta(
        days=interval_days
    )

    return {
        "due_at": due_at,
        "interval_days": interval_days,
        "repetition_count": repetition_count,
        "ease_factor": round(
            ease_factor,
            2,
        ),
    }


def _document_to_dict(
    document: Document,
    chapter_count: int,
    flashcard_count: int,
    review_count: int,
    due_count: int,
) -> dict:
    """將文件轉成頁面可直接使用的字典。"""

    return {
        "id": document.id,
        "file_name": document.file_name,
        "file_extension": document.file_extension,
        "chapter_count": chapter_count,
        "flashcard_count": flashcard_count,
        "review_count": review_count,
        "due_count": due_count,
        "created_at": document.created_at,
        "updated_at": document.updated_at,
    }


def _chapter_to_dict(
    chapter: Chapter,
    flashcard_count: int,
    review_count: int,
    due_count: int,
) -> dict:
    """將章節轉成頁面可直接使用的字典。"""

    return {
        "id": chapter.id,
        "document_id": chapter.document_id,
        "source_chapter_id": chapter.source_chapter_id,
        "chapter_order": chapter.chapter_order,
        "title": chapter.title,
        "flashcard_count": flashcard_count,
        "review_count": review_count,
        "due_count": due_count,
        "created_at": chapter.created_at,
        "updated_at": chapter.updated_at,
    }


def _flashcard_to_dict(
    flashcard: Flashcard,
    latest_review: Optional[FlashcardReview] = None,
    schedule: Optional[ReviewSchedule] = None,
) -> dict:
    """將 Flashcard 轉成頁面可直接使用的字典。"""

    latest_review_data = None

    if latest_review is not None:
        latest_review_data = {
            "id": latest_review.id,
            "familiarity_score": (
                latest_review.familiarity_score
            ),
            "familiarity_label": (
                FAMILIARITY_LABELS.get(
                    latest_review.familiarity_score,
                    str(
                        latest_review.familiarity_score
                    ),
                )
            ),
            "reviewed_at": (
                latest_review.reviewed_at
            ),
        }

    schedule_data = None

    if schedule is not None:
        schedule_data = {
            "id": schedule.id,
            "due_at": schedule.due_at,
            "interval_days": schedule.interval_days,
            "repetition_count": (
                schedule.repetition_count
            ),
            "ease_factor": schedule.ease_factor,
            "is_completed": schedule.is_completed,
        }

    return {
        "id": flashcard.id,
        "document_id": flashcard.document_id,
        "chapter_id": flashcard.chapter_id,
        "front": flashcard.front,
        "back": flashcard.back,
        "latest_review": latest_review_data,
        "schedule": schedule_data,
        "created_at": flashcard.created_at,
        "updated_at": getattr(
            flashcard,
            "updated_at",
            None,
        ),
    }


def get_flashcard_documents() -> list[dict]:
    """取得至少包含一張 Flash Card 的文件。"""

    now = _utc_now()

    with get_database_session() as session:
        chapter_count_subquery = (
            select(
                Chapter.document_id.label(
                    "document_id"
                ),
                func.count(
                    Chapter.id
                ).label(
                    "chapter_count"
                ),
            )
            .group_by(
                Chapter.document_id
            )
            .subquery()
        )

        flashcard_count_subquery = (
            select(
                Flashcard.document_id.label(
                    "document_id"
                ),
                func.count(
                    Flashcard.id
                ).label(
                    "flashcard_count"
                ),
            )
            .group_by(
                Flashcard.document_id
            )
            .subquery()
        )

        review_count_subquery = (
            select(
                Flashcard.document_id.label(
                    "document_id"
                ),
                func.count(
                    FlashcardReview.id
                ).label(
                    "review_count"
                ),
            )
            .join(
                FlashcardReview,
                FlashcardReview.flashcard_id
                == Flashcard.id,
            )
            .group_by(
                Flashcard.document_id
            )
            .subquery()
        )

        due_count_subquery = (
            select(
                ReviewSchedule.document_id.label(
                    "document_id"
                ),
                func.count(
                    ReviewSchedule.id
                ).label(
                    "due_count"
                ),
            )
            .where(
                ReviewSchedule.item_type
                == "flashcard",
                ReviewSchedule.due_at <= now,
            )
            .group_by(
                ReviewSchedule.document_id
            )
            .subquery()
        )

        statement = (
            select(
                Document,
                func.coalesce(
                    chapter_count_subquery.c.chapter_count,
                    0,
                ).label(
                    "chapter_count"
                ),
                func.coalesce(
                    flashcard_count_subquery.c.flashcard_count,
                    0,
                ).label(
                    "flashcard_count"
                ),
                func.coalesce(
                    review_count_subquery.c.review_count,
                    0,
                ).label(
                    "review_count"
                ),
                func.coalesce(
                    due_count_subquery.c.due_count,
                    0,
                ).label(
                    "due_count"
                ),
            )
            .outerjoin(
                chapter_count_subquery,
                chapter_count_subquery.c.document_id
                == Document.id,
            )
            .outerjoin(
                flashcard_count_subquery,
                flashcard_count_subquery.c.document_id
                == Document.id,
            )
            .outerjoin(
                review_count_subquery,
                review_count_subquery.c.document_id
                == Document.id,
            )
            .outerjoin(
                due_count_subquery,
                due_count_subquery.c.document_id
                == Document.id,
            )
            .where(
                func.coalesce(
                    flashcard_count_subquery.c.flashcard_count,
                    0,
                )
                > 0
            )
            .order_by(
                Document.updated_at.desc()
            )
        )

        rows = session.execute(
            statement
        ).all()

        return [
            _document_to_dict(
                document=document,
                chapter_count=_safe_int(
                    chapter_count
                ),
                flashcard_count=_safe_int(
                    flashcard_count
                ),
                review_count=_safe_int(
                    review_count
                ),
                due_count=_safe_int(
                    due_count
                ),
            )
            for (
                document,
                chapter_count,
                flashcard_count,
                review_count,
                due_count,
            ) in rows
        ]


def get_flashcard_chapters(
    document_id: int | str,
) -> list[dict]:
    """取得指定文件中包含 Flash Card 的章節。"""

    now = _utc_now()

    with get_database_session() as session:
        flashcard_count_subquery = (
            select(
                Flashcard.chapter_id.label(
                    "chapter_id"
                ),
                func.count(
                    Flashcard.id
                ).label(
                    "flashcard_count"
                ),
            )
            .where(
                Flashcard.document_id
                == document_id
            )
            .group_by(
                Flashcard.chapter_id
            )
            .subquery()
        )

        review_count_subquery = (
            select(
                Flashcard.chapter_id.label(
                    "chapter_id"
                ),
                func.count(
                    FlashcardReview.id
                ).label(
                    "review_count"
                ),
            )
            .join(
                FlashcardReview,
                FlashcardReview.flashcard_id
                == Flashcard.id,
            )
            .where(
                Flashcard.document_id
                == document_id
            )
            .group_by(
                Flashcard.chapter_id
            )
            .subquery()
        )

        due_count_subquery = (
            select(
                Flashcard.chapter_id.label(
                    "chapter_id"
                ),
                func.count(
                    ReviewSchedule.id
                ).label(
                    "due_count"
                ),
            )
            .join(
                ReviewSchedule,
                (
                    ReviewSchedule.item_type
                    == "flashcard"
                )
                & (
                    ReviewSchedule.item_id
                    == Flashcard.id
                ),
            )
            .where(
                Flashcard.document_id
                == document_id,
                ReviewSchedule.due_at <= now,
            )
            .group_by(
                Flashcard.chapter_id
            )
            .subquery()
        )

        statement = (
            select(
                Chapter,
                func.coalesce(
                    flashcard_count_subquery.c.flashcard_count,
                    0,
                ).label(
                    "flashcard_count"
                ),
                func.coalesce(
                    review_count_subquery.c.review_count,
                    0,
                ).label(
                    "review_count"
                ),
                func.coalesce(
                    due_count_subquery.c.due_count,
                    0,
                ).label(
                    "due_count"
                ),
            )
            .outerjoin(
                flashcard_count_subquery,
                flashcard_count_subquery.c.chapter_id
                == Chapter.id,
            )
            .outerjoin(
                review_count_subquery,
                review_count_subquery.c.chapter_id
                == Chapter.id,
            )
            .outerjoin(
                due_count_subquery,
                due_count_subquery.c.chapter_id
                == Chapter.id,
            )
            .where(
                Chapter.document_id
                == document_id,
                func.coalesce(
                    flashcard_count_subquery.c.flashcard_count,
                    0,
                )
                > 0,
            )
            .order_by(
                Chapter.chapter_order.asc()
            )
        )

        rows = session.execute(
            statement
        ).all()

        return [
            _chapter_to_dict(
                chapter=chapter,
                flashcard_count=_safe_int(
                    flashcard_count
                ),
                review_count=_safe_int(
                    review_count
                ),
                due_count=_safe_int(
                    due_count
                ),
            )
            for (
                chapter,
                flashcard_count,
                review_count,
                due_count,
            ) in rows
        ]


def get_flashcards_by_chapter(
    document_id: int | str,
    chapter_id: int | str,
    due_only: bool = False,
) -> list[dict]:
    """取得指定章節的 Flash Cards。"""

    now = _utc_now()

    with get_database_session() as session:
        statement = (
            select(
                Flashcard
            )
            .where(
                Flashcard.document_id
                == document_id,
                Flashcard.chapter_id
                == chapter_id,
            )
            .options(
                selectinload(
                    Flashcard.reviews
                )
            )
            .order_by(
                Flashcard.created_at.asc(),
                Flashcard.id.asc(),
            )
        )

        flashcards = session.execute(
            statement
        ).scalars().unique().all()

        if not flashcards:
            return []

        flashcard_ids = [
            flashcard.id
            for flashcard in flashcards
        ]

        schedule_statement = (
            select(
                ReviewSchedule
            )
            .where(
                ReviewSchedule.item_type
                == "flashcard",
                ReviewSchedule.item_id.in_(
                    flashcard_ids
                ),
            )
        )

        schedules = session.execute(
            schedule_statement
        ).scalars().all()

        schedule_map = {
            schedule.item_id: schedule
            for schedule in schedules
        }

        results = []

        for flashcard in flashcards:
            reviews = sorted(
                flashcard.reviews or [],
                key=lambda review: (
                    review.reviewed_at
                    or datetime.min
                ),
                reverse=True,
            )

            schedule = schedule_map.get(
                flashcard.id
            )

            if due_only:
                if (
                    schedule is not None
                    and schedule.due_at > now
                ):
                    continue

            results.append(
                _flashcard_to_dict(
                    flashcard=flashcard,
                    latest_review=(
                        reviews[0]
                        if reviews
                        else None
                    ),
                    schedule=schedule,
                )
            )

        return results


def save_flashcard_review(
    flashcard_id: int | str,
    familiarity_score: int | str,
) -> dict:
    """
    儲存 Flash Card 複習結果並更新複習排程。
    """

    normalized_score = (
        _normalize_familiarity_score(
            familiarity_score
        )
    )

    with get_database_session() as session:
        flashcard = session.get(
            Flashcard,
            flashcard_id,
        )

        if flashcard is None:
            raise ValueError(
                "找不到指定的 Flash Card。"
            )

        now = _utc_now()

        review = FlashcardReview(
            flashcard_id=flashcard.id,
            familiarity_score=normalized_score,
            reviewed_at=now,
        )

        session.add(
            review
        )

        schedule_statement = (
            select(
                ReviewSchedule
            )
            .where(
                ReviewSchedule.item_type
                == "flashcard",
                ReviewSchedule.item_id
                == flashcard.id,
            )
        )

        schedule = session.execute(
            schedule_statement
        ).scalars().first()

        schedule_data = (
            _calculate_next_schedule(
                familiarity_score=normalized_score,
                previous_schedule=schedule,
            )
        )

        if schedule is None:
            schedule = ReviewSchedule(
                item_type="flashcard",
                item_id=flashcard.id,
                document_id=flashcard.document_id,
                due_at=schedule_data[
                    "due_at"
                ],
                interval_days=schedule_data[
                    "interval_days"
                ],
                repetition_count=schedule_data[
                    "repetition_count"
                ],
                ease_factor=schedule_data[
                    "ease_factor"
                ],
                is_completed=False,
                created_at=now,
                updated_at=now,
            )

            session.add(
                schedule
            )

        else:
            schedule.document_id = (
                flashcard.document_id
            )

            schedule.due_at = (
                schedule_data["due_at"]
            )

            schedule.interval_days = (
                schedule_data[
                    "interval_days"
                ]
            )

            schedule.repetition_count = (
                schedule_data[
                    "repetition_count"
                ]
            )

            schedule.ease_factor = (
                schedule_data[
                    "ease_factor"
                ]
            )

            schedule.is_completed = False
            schedule.updated_at = now

        session.commit()

        session.refresh(
            review
        )

        session.refresh(
            schedule
        )

        return {
            "saved": True,
            "review": {
                "id": review.id,
                "flashcard_id": (
                    review.flashcard_id
                ),
                "familiarity_score": (
                    review.familiarity_score
                ),
                "familiarity_label": (
                    FAMILIARITY_LABELS[
                        review.familiarity_score
                    ]
                ),
                "reviewed_at": (
                    review.reviewed_at
                ),
            },
            "schedule": {
                "id": schedule.id,
                "due_at": schedule.due_at,
                "interval_days": (
                    schedule.interval_days
                ),
                "repetition_count": (
                    schedule.repetition_count
                ),
                "ease_factor": (
                    schedule.ease_factor
                ),
            },
        }


def get_flashcard_review_history(
    document_id: int | str,
    chapter_id: Optional[int | str] = None,
    limit: int = 100,
) -> list[dict]:
    """取得 Flash Card 複習紀錄。"""

    safe_limit = max(
        min(
            _safe_int(
                limit,
                100,
            ),
            500,
        ),
        1,
    )

    with get_database_session() as session:
        statement = (
            select(
                FlashcardReview,
                Flashcard,
                Chapter,
                Document,
            )
            .join(
                Flashcard,
                FlashcardReview.flashcard_id
                == Flashcard.id,
            )
            .outerjoin(
                Chapter,
                Flashcard.chapter_id
                == Chapter.id,
            )
            .join(
                Document,
                Flashcard.document_id
                == Document.id,
            )
            .where(
                Flashcard.document_id
                == document_id
            )
        )

        if chapter_id is not None:
            statement = statement.where(
                Flashcard.chapter_id
                == chapter_id
            )

        statement = (
            statement
            .order_by(
                FlashcardReview.reviewed_at.desc()
            )
            .limit(
                safe_limit
            )
        )

        rows = session.execute(
            statement
        ).all()

        return [
            {
                "id": review.id,
                "flashcard_id": flashcard.id,
                "document_id": (
                    flashcard.document_id
                ),
                "document_name": (
                    document.file_name
                ),
                "chapter_id": (
                    flashcard.chapter_id
                ),
                "chapter_title": (
                    chapter.title
                    if chapter is not None
                    else ""
                ),
                "chapter_order": (
                    chapter.chapter_order
                    if chapter is not None
                    else None
                ),
                "front": flashcard.front,
                "back": flashcard.back,
                "familiarity_score": (
                    review.familiarity_score
                ),
                "familiarity_label": (
                    FAMILIARITY_LABELS.get(
                        review.familiarity_score,
                        str(
                            review.familiarity_score
                        ),
                    )
                ),
                "reviewed_at": (
                    review.reviewed_at
                ),
            }
            for (
                review,
                flashcard,
                chapter,
                document,
            ) in rows
        ]


def get_flashcard_summary(
    document_id: int | str,
    chapter_id: Optional[int | str] = None,
) -> dict:
    """取得 Flash Card 複習統計。"""

    now = _utc_now()

    with get_database_session() as session:
        flashcard_filters = [
            Flashcard.document_id
            == document_id
        ]

        if chapter_id is not None:
            flashcard_filters.append(
                Flashcard.chapter_id
                == chapter_id
            )

        flashcard_count = (
            session.query(
                func.count(
                    Flashcard.id
                )
            )
            .filter(
                *flashcard_filters
            )
            .scalar()
            or 0
        )

        review_rows = (
            session.query(
                FlashcardReview.familiarity_score,
                func.count(
                    FlashcardReview.id
                ),
            )
            .join(
                Flashcard,
                FlashcardReview.flashcard_id
                == Flashcard.id,
            )
            .filter(
                *flashcard_filters
            )
            .group_by(
                FlashcardReview.familiarity_score
            )
            .all()
        )

        score_counts = {
            score: 0
            for score in range(6)
        }

        for score, count in review_rows:
            normalized_score = _safe_int(
                score,
                0,
            )

            if normalized_score in score_counts:
                score_counts[
                    normalized_score
                ] = _safe_int(
                    count,
                    0,
                )

        review_count = sum(
            score_counts.values()
        )

        total_score = sum(
            score * count
            for score, count
            in score_counts.items()
        )

        average_score = (
            round(
                total_score
                / review_count,
                2,
            )
            if review_count > 0
            else 0.0
        )

        due_statement = (
            select(
                func.count(
                    ReviewSchedule.id
                )
            )
            .join(
                Flashcard,
                (
                    ReviewSchedule.item_type
                    == "flashcard"
                )
                & (
                    ReviewSchedule.item_id
                    == Flashcard.id
                ),
            )
            .where(
                *flashcard_filters,
                ReviewSchedule.due_at <= now,
            )
        )

        due_count = (
            session.execute(
                due_statement
            ).scalar()
            or 0
        )

        reviewed_flashcard_count = (
            session.query(
                func.count(
                    func.distinct(
                        FlashcardReview.flashcard_id
                    )
                )
            )
            .join(
                Flashcard,
                FlashcardReview.flashcard_id
                == Flashcard.id,
            )
            .filter(
                *flashcard_filters
            )
            .scalar()
            or 0
        )

        unreviewed_count = max(
            _safe_int(
                flashcard_count
            )
            - _safe_int(
                reviewed_flashcard_count
            ),
            0,
        )

        return {
            "document_id": str(
                document_id
            ),
            "chapter_id": (
                str(chapter_id)
                if chapter_id is not None
                else None
            ),
            "flashcard_count": _safe_int(
                flashcard_count
            ),
            "review_count": review_count,
            "reviewed_flashcard_count": (
                _safe_int(
                    reviewed_flashcard_count
                )
            ),
            "unreviewed_count": (
                unreviewed_count
            ),
            "due_count": _safe_int(
                due_count
            ),
            "average_familiarity_score": (
                average_score
            ),
            "score_counts": score_counts,
        }
