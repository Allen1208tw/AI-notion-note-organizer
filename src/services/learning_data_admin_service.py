from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import delete, func, select

from src.database.database import get_database_session
from src.database.models import (
    Chapter,
    Document,
    Flashcard,
    FlashcardReview,
    Quiz,
    QuizAttempt,
    ReviewSchedule,
    WeakPoint,
    utc_now,
)
from src.services.learning_item_identity import (
    flashcard_identity,
    quiz_identity,
)


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


def _utc_now() -> datetime:
    """取得目前 UTC 時間。"""

    return utc_now()


def _group_duplicate_quizzes(quizzes: list[Quiz]) -> list[list[Quiz]]:
    groups: dict[tuple[str, str], list[Quiz]] = {}

    for quiz in quizzes:
        key = (
            _safe_text(quiz.chapter_id),
            quiz_identity(quiz.question, quiz.correct_answer),
        )
        groups.setdefault(key, []).append(quiz)

    return [items for items in groups.values() if len(items) > 1]


def _group_duplicate_flashcards(
    flashcards: list[Flashcard],
) -> list[list[Flashcard]]:
    groups: dict[tuple[str, str], list[Flashcard]] = {}

    for card in flashcards:
        key = (
            _safe_text(card.chapter_id),
            flashcard_identity(card.front, card.back),
        )
        groups.setdefault(key, []).append(card)

    return [items for items in groups.values() if len(items) > 1]


def _duplicate_summary(session, document_id: int | str) -> dict:
    quiz_groups = _group_duplicate_quizzes(
        session.query(Quiz)
        .filter(Quiz.document_id == document_id)
        .order_by(Quiz.created_at.asc(), Quiz.id.asc())
        .all()
    )
    flashcard_groups = _group_duplicate_flashcards(
        session.query(Flashcard)
        .filter(Flashcard.document_id == document_id)
        .order_by(Flashcard.created_at.asc(), Flashcard.id.asc())
        .all()
    )

    return {
        "quiz_groups": quiz_groups,
        "flashcard_groups": flashcard_groups,
        "duplicate_quiz_group_count": len(quiz_groups),
        "duplicate_quiz_count": sum(len(group) - 1 for group in quiz_groups),
        "duplicate_flashcard_group_count": len(flashcard_groups),
        "duplicate_flashcard_count": sum(
            len(group) - 1 for group in flashcard_groups
        ),
    }


def _merge_review_schedules(
    session,
    item_type: str,
    canonical_id: str,
    duplicate_id: str,
) -> int:
    canonical_schedules = (
        session.query(ReviewSchedule)
        .filter(
            ReviewSchedule.item_type == item_type,
            ReviewSchedule.item_id == canonical_id,
        )
        .order_by(ReviewSchedule.created_at.asc())
        .all()
    )
    duplicate_schedules = (
        session.query(ReviewSchedule)
        .filter(
            ReviewSchedule.item_type == item_type,
            ReviewSchedule.item_id == duplicate_id,
        )
        .order_by(ReviewSchedule.created_at.asc())
        .all()
    )

    if not duplicate_schedules:
        return 0

    if not canonical_schedules:
        duplicate_schedules[0].item_id = canonical_id
        canonical_schedules = [duplicate_schedules[0]]
        duplicate_schedules = duplicate_schedules[1:]

    canonical = canonical_schedules[0]
    redundant = canonical_schedules[1:] + duplicate_schedules

    for schedule in redundant:
        canonical.due_at = min(canonical.due_at, schedule.due_at)
        canonical.interval_days = max(
            canonical.interval_days,
            schedule.interval_days,
        )
        canonical.repetition_count = max(
            canonical.repetition_count,
            schedule.repetition_count,
        )
        canonical.ease_factor = max(canonical.ease_factor, schedule.ease_factor)
        canonical.is_completed = (
            canonical.is_completed and schedule.is_completed
        )
        canonical.updated_at = max(canonical.updated_at, schedule.updated_at)
        session.delete(schedule)

    return len(redundant)


def deduplicate_document_learning_items(
    document_id: int | str,
    preview_only: bool = True,
) -> dict:
    """Merge duplicate learning items while preserving their history."""

    with get_database_session() as session:
        document = session.get(Document, document_id)

        if document is None:
            raise ValueError("找不到指定文件。")

        duplicates = _duplicate_summary(session, document_id)
        result = {
            "document_id": _safe_text(document_id),
            "document_name": document.file_name,
            "preview_only": preview_only,
            "duplicate_quiz_group_count": duplicates[
                "duplicate_quiz_group_count"
            ],
            "duplicate_quiz_count": duplicates["duplicate_quiz_count"],
            "duplicate_flashcard_group_count": duplicates[
                "duplicate_flashcard_group_count"
            ],
            "duplicate_flashcard_count": duplicates[
                "duplicate_flashcard_count"
            ],
            "merged_quiz_count": 0,
            "merged_flashcard_count": 0,
            "moved_quiz_attempt_count": 0,
            "moved_flashcard_review_count": 0,
            "merged_schedule_count": 0,
            "merged_weak_point_count": 0,
        }

        if preview_only:
            return result

        try:
            for group in duplicates["quiz_groups"]:
                reference_counts = {
                    quiz.id: (
                        session.query(func.count(QuizAttempt.id))
                        .filter(QuizAttempt.quiz_id == quiz.id)
                        .scalar()
                        or 0
                    )
                    + (
                        session.query(func.count(WeakPoint.id))
                        .filter(WeakPoint.quiz_id == quiz.id)
                        .scalar()
                        or 0
                    )
                    for quiz in group
                }
                canonical = sorted(
                    group,
                    key=lambda quiz: (
                        -reference_counts[quiz.id],
                        quiz.created_at,
                        quiz.id,
                    ),
                )[0]

                for duplicate in group:
                    if duplicate.id == canonical.id:
                        continue

                    moved_attempts = (
                        session.query(QuizAttempt)
                        .filter(QuizAttempt.quiz_id == duplicate.id)
                        .update(
                            {QuizAttempt.quiz_id: canonical.id},
                            synchronize_session=False,
                        )
                    )
                    result["moved_quiz_attempt_count"] += moved_attempts

                    canonical_weak = (
                        session.query(WeakPoint)
                        .filter(WeakPoint.quiz_id == canonical.id)
                        .first()
                    )
                    duplicate_weak = (
                        session.query(WeakPoint)
                        .filter(WeakPoint.quiz_id == duplicate.id)
                        .first()
                    )

                    if duplicate_weak and canonical_weak:
                        canonical_weak.wrong_count += duplicate_weak.wrong_count
                        canonical_weak.partial_count += duplicate_weak.partial_count
                        canonical_weak.correct_count += duplicate_weak.correct_count
                        canonical_weak.weakness_score = max(
                            canonical_weak.weakness_score,
                            duplicate_weak.weakness_score,
                        )
                        status_order = {"active": 2, "improving": 1, "mastered": 0}
                        canonical_weak.status = max(
                            (canonical_weak.status, duplicate_weak.status),
                            key=lambda value: status_order.get(value, 2),
                        )
                        if duplicate_weak.updated_at >= canonical_weak.updated_at:
                            canonical_weak.last_answer = duplicate_weak.last_answer
                        canonical_weak.updated_at = max(
                            canonical_weak.updated_at,
                            duplicate_weak.updated_at,
                        )
                        session.delete(duplicate_weak)
                        result["merged_weak_point_count"] += 1
                    elif duplicate_weak:
                        duplicate_weak.quiz_id = canonical.id

                    result["merged_schedule_count"] += _merge_review_schedules(
                        session,
                        "quiz",
                        canonical.id,
                        duplicate.id,
                    )
                    session.delete(duplicate)
                    result["merged_quiz_count"] += 1

            for group in duplicates["flashcard_groups"]:
                reference_counts = {
                    card.id: (
                        session.query(func.count(FlashcardReview.id))
                        .filter(FlashcardReview.flashcard_id == card.id)
                        .scalar()
                        or 0
                    )
                    for card in group
                }
                canonical = sorted(
                    group,
                    key=lambda card: (
                        -reference_counts[card.id],
                        card.created_at,
                        card.id,
                    ),
                )[0]

                for duplicate in group:
                    if duplicate.id == canonical.id:
                        continue

                    moved_reviews = (
                        session.query(FlashcardReview)
                        .filter(FlashcardReview.flashcard_id == duplicate.id)
                        .update(
                            {FlashcardReview.flashcard_id: canonical.id},
                            synchronize_session=False,
                        )
                    )
                    result["moved_flashcard_review_count"] += moved_reviews
                    result["merged_schedule_count"] += _merge_review_schedules(
                        session,
                        "flashcard",
                        canonical.id,
                        duplicate.id,
                    )
                    session.delete(duplicate)
                    result["merged_flashcard_count"] += 1

            session.flush()
            session.commit()
            return result
        except Exception:
            session.rollback()
            raise


def get_all_learning_documents() -> list[dict]:
    """
    取得所有 SQLite 文件及學習資料統計。

    用於：
    - 管理頁面
    - 資料診斷
    - 文件刪除
    - 確認 Quiz / Flash Card 是否正確寫入
    """

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

        quiz_count_subquery = (
            select(
                Quiz.document_id.label(
                    "document_id"
                ),
                func.count(
                    Quiz.id
                ).label(
                    "quiz_count"
                ),
            )
            .group_by(
                Quiz.document_id
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

        quiz_attempt_count_subquery = (
            select(
                Quiz.document_id.label(
                    "document_id"
                ),
                func.count(
                    QuizAttempt.id
                ).label(
                    "quiz_attempt_count"
                ),
            )
            .join(
                QuizAttempt,
                QuizAttempt.quiz_id == Quiz.id,
            )
            .group_by(
                Quiz.document_id
            )
            .subquery()
        )

        flashcard_review_count_subquery = (
            select(
                Flashcard.document_id.label(
                    "document_id"
                ),
                func.count(
                    FlashcardReview.id
                ).label(
                    "flashcard_review_count"
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

        weak_point_count_subquery = (
            select(
                WeakPoint.document_id.label(
                    "document_id"
                ),
                func.count(
                    WeakPoint.id
                ).label(
                    "weak_point_count"
                ),
            )
            .group_by(
                WeakPoint.document_id
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
                    quiz_count_subquery.c.quiz_count,
                    0,
                ).label(
                    "quiz_count"
                ),
                func.coalesce(
                    flashcard_count_subquery.c.flashcard_count,
                    0,
                ).label(
                    "flashcard_count"
                ),
                func.coalesce(
                    quiz_attempt_count_subquery.c.quiz_attempt_count,
                    0,
                ).label(
                    "quiz_attempt_count"
                ),
                func.coalesce(
                    flashcard_review_count_subquery.c.flashcard_review_count,
                    0,
                ).label(
                    "flashcard_review_count"
                ),
                func.coalesce(
                    weak_point_count_subquery.c.weak_point_count,
                    0,
                ).label(
                    "weak_point_count"
                ),
            )
            .outerjoin(
                chapter_count_subquery,
                chapter_count_subquery.c.document_id
                == Document.id,
            )
            .outerjoin(
                quiz_count_subquery,
                quiz_count_subquery.c.document_id
                == Document.id,
            )
            .outerjoin(
                flashcard_count_subquery,
                flashcard_count_subquery.c.document_id
                == Document.id,
            )
            .outerjoin(
                quiz_attempt_count_subquery,
                quiz_attempt_count_subquery.c.document_id
                == Document.id,
            )
            .outerjoin(
                flashcard_review_count_subquery,
                flashcard_review_count_subquery.c.document_id
                == Document.id,
            )
            .outerjoin(
                weak_point_count_subquery,
                weak_point_count_subquery.c.document_id
                == Document.id,
            )
            .order_by(
                Document.updated_at.desc()
            )
        )

        rows = session.execute(
            statement
        ).all()

        return [
            {
                "id": document.id,
                "file_name": document.file_name,
                "file_extension": document.file_extension,
                "status": document.status,
                "export_status": getattr(
                    document,
                    "export_status",
                    "pending",
                ),
                "chapter_count": _safe_int(
                    chapter_count
                ),
                "quiz_count": _safe_int(
                    quiz_count
                ),
                "flashcard_count": _safe_int(
                    flashcard_count
                ),
                "quiz_attempt_count": _safe_int(
                    quiz_attempt_count
                ),
                "flashcard_review_count": _safe_int(
                    flashcard_review_count
                ),
                "weak_point_count": _safe_int(
                    weak_point_count
                ),
                "created_at": document.created_at,
                "updated_at": document.updated_at,
            }
            for (
                document,
                chapter_count,
                quiz_count,
                flashcard_count,
                quiz_attempt_count,
                flashcard_review_count,
                weak_point_count,
            ) in rows
        ]


def get_document_diagnostics(
    document_id: int | str,
) -> dict:
    """
    診斷單一文件的 SQLite 資料完整性。

    檢查：
    - 章節是否存在
    - source_chapter_id 是否重複
    - 是否有空白章節標題
    - Quiz / Flash Card 是否集中在單一章節
    - 是否存在沒有父項目的學習紀錄
    - 每章 Quiz / Flash Card 數量
    """

    with get_database_session() as session:
        document = session.get(
            Document,
            document_id,
        )

        if document is None:
            raise ValueError(
                "找不到指定文件。"
            )

        chapter_statement = (
            select(
                Chapter
            )
            .where(
                Chapter.document_id
                == document_id
            )
            .order_by(
                Chapter.chapter_order.asc(),
                Chapter.id.asc(),
            )
        )

        chapters = session.execute(
            chapter_statement
        ).scalars().all()

        chapter_rows = []

        source_id_counts: dict[str, int] = {}

        for chapter in chapters:
            source_id = _safe_text(
                chapter.source_chapter_id
            )

            source_id_counts[source_id] = (
                source_id_counts.get(
                    source_id,
                    0,
                )
                + 1
            )

            quiz_count = (
                session.query(
                    func.count(
                        Quiz.id
                    )
                )
                .filter(
                    Quiz.chapter_id
                    == chapter.id
                )
                .scalar()
                or 0
            )

            flashcard_count = (
                session.query(
                    func.count(
                        Flashcard.id
                    )
                )
                .filter(
                    Flashcard.chapter_id
                    == chapter.id
                )
                .scalar()
                or 0
            )

            chapter_rows.append(
                {
                    "id": chapter.id,
                    "source_chapter_id": (
                        source_id
                    ),
                    "chapter_order": (
                        chapter.chapter_order
                    ),
                    "title": chapter.title,
                    "quiz_count": _safe_int(
                        quiz_count
                    ),
                    "flashcard_count": _safe_int(
                        flashcard_count
                    ),
                    "created_at": chapter.created_at,
                    "updated_at": chapter.updated_at,
                }
            )

        duplicate_source_ids = [
            source_id
            for source_id, count
            in source_id_counts.items()
            if (
                source_id
                and count > 1
            )
        ]

        empty_title_chapters = [
            item
            for item in chapter_rows
            if not _safe_text(
                item.get("title")
            ).strip()
        ]

        chapters_with_learning_data = [
            item
            for item in chapter_rows
            if (
                _safe_int(
                    item.get("quiz_count")
                )
                > 0
                or _safe_int(
                    item.get("flashcard_count")
                )
                > 0
            )
        ]

        total_quiz_count = sum(
            _safe_int(
                item.get("quiz_count")
            )
            for item in chapter_rows
        )

        total_flashcard_count = sum(
            _safe_int(
                item.get("flashcard_count")
            )
            for item in chapter_rows
        )

        quiz_distribution_warning = (
            len(chapter_rows) > 1
            and total_quiz_count > 0
            and len(
                [
                    item
                    for item in chapter_rows
                    if _safe_int(
                        item.get("quiz_count")
                    )
                    > 0
                ]
            )
            == 1
        )

        flashcard_distribution_warning = (
            len(chapter_rows) > 1
            and total_flashcard_count > 0
            and len(
                [
                    item
                    for item in chapter_rows
                    if _safe_int(
                        item.get(
                            "flashcard_count"
                        )
                    )
                    > 0
                ]
            )
            == 1
        )

        orphan_quiz_attempt_count = (
            session.query(
                func.count(
                    QuizAttempt.id
                )
            )
            .outerjoin(
                Quiz,
                QuizAttempt.quiz_id
                == Quiz.id,
            )
            .filter(
                Quiz.id.is_(None)
            )
            .scalar()
            or 0
        )

        orphan_flashcard_review_count = (
            session.query(
                func.count(
                    FlashcardReview.id
                )
            )
            .outerjoin(
                Flashcard,
                FlashcardReview.flashcard_id
                == Flashcard.id,
            )
            .filter(
                Flashcard.id.is_(None)
            )
            .scalar()
            or 0
        )

        duplicate_items = _duplicate_summary(
            session,
            document_id,
        )

        warnings = []

        if not chapters:
            warnings.append(
                "文件沒有任何章節資料。"
            )

        if duplicate_source_ids:
            warnings.append(
                "偵測到重複的 source_chapter_id："
                + ", ".join(
                    duplicate_source_ids
                )
            )

        if empty_title_chapters:
            warnings.append(
                "存在空白章節標題。"
            )

        if quiz_distribution_warning:
            warnings.append(
                "Quiz 只集中在單一章節，"
                "可能存在章節 ID 對應問題。"
            )

        if flashcard_distribution_warning:
            warnings.append(
                "Flash Cards 只集中在單一章節，"
                "可能存在章節 ID 對應問題。"
            )

        if orphan_quiz_attempt_count > 0:
            warnings.append(
                "存在找不到 Quiz 的作答紀錄。"
            )

        if orphan_flashcard_review_count > 0:
            warnings.append(
                "存在找不到 Flash Card 的複習紀錄。"
            )

        if duplicate_items["duplicate_quiz_count"] > 0:
            warnings.append(
                "存在重複 Quiz："
                f"{duplicate_items['duplicate_quiz_count']} 題可安全合併。"
            )

        if duplicate_items["duplicate_flashcard_count"] > 0:
            warnings.append(
                "存在重複 Flash Cards："
                f"{duplicate_items['duplicate_flashcard_count']} 張可安全合併。"
            )

        return {
            "document": {
                "id": document.id,
                "file_name": document.file_name,
                "file_extension": document.file_extension,
                "status": document.status,
                "export_status": getattr(
                    document,
                    "export_status",
                    "pending",
                ),
                "created_at": document.created_at,
                "updated_at": document.updated_at,
            },
            "summary": {
                "chapter_count": len(
                    chapter_rows
                ),
                "chapter_with_learning_data_count": (
                    len(
                        chapters_with_learning_data
                    )
                ),
                "quiz_count": total_quiz_count,
                "flashcard_count": (
                    total_flashcard_count
                ),
                "duplicate_source_id_count": (
                    len(
                        duplicate_source_ids
                    )
                ),
                "orphan_quiz_attempt_count": (
                    _safe_int(
                        orphan_quiz_attempt_count
                    )
                ),
                "orphan_flashcard_review_count": (
                    _safe_int(
                        orphan_flashcard_review_count
                    )
                ),
                "duplicate_quiz_count": duplicate_items[
                    "duplicate_quiz_count"
                ],
                "duplicate_flashcard_count": duplicate_items[
                    "duplicate_flashcard_count"
                ],
            },
            "chapters": chapter_rows,
            "warnings": warnings,
            "is_healthy": len(warnings) == 0,
            "checked_at": _utc_now(),
        }


def delete_document_learning_data(
    document_id: int | str,
    delete_document_record: bool = False,
) -> dict:
    """
    刪除單一文件的學習資料。

    預設保留 documents 主紀錄，只刪除：
    - QuizAttempt
    - FlashcardReview
    - ReviewSchedule
    - WeakPoint
    - Quiz
    - Flashcard
    - Chapter

    delete_document_record=True 時連 Document 一併刪除。
    """

    with get_database_session() as session:
        document = session.get(
            Document,
            document_id,
        )

        if document is None:
            raise ValueError(
                "找不到指定文件。"
            )

        quiz_ids = session.execute(
            select(
                Quiz.id
            ).where(
                Quiz.document_id
                == document_id
            )
        ).scalars().all()

        flashcard_ids = session.execute(
            select(
                Flashcard.id
            ).where(
                Flashcard.document_id
                == document_id
            )
        ).scalars().all()

        deleted_counts = {
            "quiz_attempts": 0,
            "flashcard_reviews": 0,
            "review_schedules": 0,
            "weak_points": 0,
            "quizzes": 0,
            "flashcards": 0,
            "chapters": 0,
            "documents": 0,
        }

        if quiz_ids:
            result = session.execute(
                delete(
                    QuizAttempt
                ).where(
                    QuizAttempt.quiz_id.in_(
                        quiz_ids
                    )
                )
            )

            deleted_counts[
                "quiz_attempts"
            ] = result.rowcount or 0

        if flashcard_ids:
            result = session.execute(
                delete(
                    FlashcardReview
                ).where(
                    FlashcardReview.flashcard_id.in_(
                        flashcard_ids
                    )
                )
            )

            deleted_counts[
                "flashcard_reviews"
            ] = result.rowcount or 0

            result = session.execute(
                delete(
                    ReviewSchedule
                ).where(
                    ReviewSchedule.item_type
                    == "flashcard",
                    ReviewSchedule.item_id.in_(
                        flashcard_ids
                    ),
                )
            )

            deleted_counts[
                "review_schedules"
            ] = result.rowcount or 0

        result = session.execute(
            delete(
                WeakPoint
            ).where(
                WeakPoint.document_id
                == document_id
            )
        )

        deleted_counts[
            "weak_points"
        ] = result.rowcount or 0

        result = session.execute(
            delete(
                Quiz
            ).where(
                Quiz.document_id
                == document_id
            )
        )

        deleted_counts[
            "quizzes"
        ] = result.rowcount or 0

        result = session.execute(
            delete(
                Flashcard
            ).where(
                Flashcard.document_id
                == document_id
            )
        )

        deleted_counts[
            "flashcards"
        ] = result.rowcount or 0

        result = session.execute(
            delete(
                Chapter
            ).where(
                Chapter.document_id
                == document_id
            )
        )

        deleted_counts[
            "chapters"
        ] = result.rowcount or 0

        if delete_document_record:
            result = session.execute(
                delete(
                    Document
                ).where(
                    Document.id
                    == document_id
                )
            )

            deleted_counts[
                "documents"
            ] = result.rowcount or 0

        else:
            document.status = "parsed"
            document.export_status = "pending"
            document.updated_at = _utc_now()

        session.commit()

        return {
            "deleted": True,
            "document_id": _safe_text(
                document_id
            ),
            "document_name": document.file_name,
            "delete_document_record": (
                delete_document_record
            ),
            "deleted_counts": deleted_counts,
        }


def delete_single_chapter_learning_data(
    document_id: int | str,
    chapter_id: int | str,
) -> dict:
    """
    刪除指定章節的 Quiz、Flash Cards 與相關紀錄。

    保留章節主紀錄，方便重新同步該章快取。
    """

    with get_database_session() as session:
        chapter = session.get(
            Chapter,
            chapter_id,
        )

        if (
            chapter is None
            or _safe_text(
                chapter.document_id
            )
            != _safe_text(
                document_id
            )
        ):
            raise ValueError(
                "找不到指定章節。"
            )

        quiz_ids = session.execute(
            select(
                Quiz.id
            ).where(
                Quiz.chapter_id
                == chapter_id
            )
        ).scalars().all()

        flashcard_ids = session.execute(
            select(
                Flashcard.id
            ).where(
                Flashcard.chapter_id
                == chapter_id
            )
        ).scalars().all()

        deleted_counts = {
            "quiz_attempts": 0,
            "flashcard_reviews": 0,
            "review_schedules": 0,
            "weak_points": 0,
            "quizzes": 0,
            "flashcards": 0,
        }

        if quiz_ids:
            result = session.execute(
                delete(
                    QuizAttempt
                ).where(
                    QuizAttempt.quiz_id.in_(
                        quiz_ids
                    )
                )
            )

            deleted_counts[
                "quiz_attempts"
            ] = result.rowcount or 0

        if flashcard_ids:
            result = session.execute(
                delete(
                    FlashcardReview
                ).where(
                    FlashcardReview.flashcard_id.in_(
                        flashcard_ids
                    )
                )
            )

            deleted_counts[
                "flashcard_reviews"
            ] = result.rowcount or 0

            result = session.execute(
                delete(
                    ReviewSchedule
                ).where(
                    ReviewSchedule.item_type
                    == "flashcard",
                    ReviewSchedule.item_id.in_(
                        flashcard_ids
                    ),
                )
            )

            deleted_counts[
                "review_schedules"
            ] = result.rowcount or 0

        result = session.execute(
            delete(
                WeakPoint
            ).where(
                WeakPoint.chapter_id
                == chapter_id
            )
        )

        deleted_counts[
            "weak_points"
        ] = result.rowcount or 0

        result = session.execute(
            delete(
                Quiz
            ).where(
                Quiz.chapter_id
                == chapter_id
            )
        )

        deleted_counts[
            "quizzes"
        ] = result.rowcount or 0

        result = session.execute(
            delete(
                Flashcard
            ).where(
                Flashcard.chapter_id
                == chapter_id
            )
        )

        deleted_counts[
            "flashcards"
        ] = result.rowcount or 0

        session.commit()

        return {
            "deleted": True,
            "document_id": _safe_text(
                document_id
            ),
            "chapter_id": _safe_text(
                chapter_id
            ),
            "chapter_title": chapter.title,
            "deleted_counts": deleted_counts,
        }
