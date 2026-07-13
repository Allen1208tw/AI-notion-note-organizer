from __future__ import annotations

from datetime import datetime
from typing import Iterable, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from src.database.database import get_database_session
from src.database.models import (
    Chapter,
    Document,
    Quiz,
    QuizAttempt,
    WeakPoint,
)


VALID_SELF_RATINGS = {
    "correct",
    "partial",
    "wrong",
}

SELF_RATING_ALIASES = {
    "correct": "correct",
    "right": "correct",
    "true": "correct",
    "答對": "correct",
    "正確": "correct",
    "會": "correct",
    "partial": "partial",
    "partially_correct": "partial",
    "部分答對": "partial",
    "部分正確": "partial",
    "不完全": "partial",
    "wrong": "wrong",
    "incorrect": "wrong",
    "false": "wrong",
    "答錯": "wrong",
    "錯誤": "wrong",
    "不會": "wrong",
}

SELF_RATING_SCORES = {
    "correct": 2,
    "partial": 1,
    "wrong": 0,
}

SELF_RATING_LABELS = {
    "correct": "答對",
    "partial": "部分答對",
    "wrong": "答錯",
}

WEAK_POINT_ACTIVE = "active"
WEAK_POINT_IMPROVING = "improving"
WEAK_POINT_MASTERED = "mastered"

VALID_WEAK_POINT_STATUSES = {
    WEAK_POINT_ACTIVE,
    WEAK_POINT_IMPROVING,
    WEAK_POINT_MASTERED,
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


def _normalize_self_rating(self_rating: str) -> str:
    """統一自評值並驗證。"""

    normalized = _safe_text(
        self_rating
    ).strip().lower()

    normalized = SELF_RATING_ALIASES.get(
        normalized,
        normalized,
    )

    if normalized not in VALID_SELF_RATINGS:
        raise ValueError(
            "self_rating 必須是 correct、partial、wrong，"
            "或答對、部分答對、答錯。"
        )

    return normalized


def _normalize_statuses(
    statuses: Optional[Iterable[str]],
) -> list[str]:
    """整理弱點狀態篩選條件。"""

    if statuses is None:
        return []

    normalized_statuses = []

    for status in statuses:
        normalized = _safe_text(
            status
        ).strip().lower()

        if normalized in VALID_WEAK_POINT_STATUSES:
            normalized_statuses.append(
                normalized
            )

    return list(dict.fromkeys(
        normalized_statuses
    ))


def _document_to_dict(
    document: Document,
    chapter_count: int = 0,
    quiz_count: int = 0,
    attempt_count: int = 0,
    weak_point_count: int = 0,
) -> dict:
    """將 Document 轉成頁面可直接使用的字典。"""

    return {
        "id": document.id,
        "file_name": document.file_name,
        "file_extension": document.file_extension,
        "status": document.status,
        "export_status": getattr(
            document,
            "export_status",
            "pending",
        ),
        "chapter_count": chapter_count,
        "quiz_count": quiz_count,
        "attempt_count": attempt_count,
        "weak_point_count": weak_point_count,
        "created_at": document.created_at,
        "updated_at": document.updated_at,
    }


def _chapter_to_dict(
    chapter: Chapter,
    quiz_count: int = 0,
    attempt_count: int = 0,
    weak_point_count: int = 0,
) -> dict:
    """將 Chapter 轉成頁面可直接使用的字典。"""

    return {
        "id": chapter.id,
        "document_id": chapter.document_id,
        "source_chapter_id": chapter.source_chapter_id,
        "chapter_order": chapter.chapter_order,
        "title": chapter.title,
        "character_count": chapter.character_count,
        "subsection_count": getattr(
            chapter,
            "subsection_count",
            0,
        ),
        "quiz_count": quiz_count,
        "attempt_count": attempt_count,
        "weak_point_count": weak_point_count,
        "created_at": chapter.created_at,
        "updated_at": chapter.updated_at,
    }


def _quiz_to_dict(
    quiz: Quiz,
    attempt_count: int = 0,
    latest_attempt: Optional[QuizAttempt] = None,
    weak_point: Optional[WeakPoint] = None,
) -> dict:
    """將 Quiz 轉成頁面可直接使用的字典。"""

    latest_attempt_data = None

    if latest_attempt is not None:
        latest_attempt_data = {
            "id": latest_attempt.id,
            "user_answer": latest_attempt.user_answer,
            "self_rating": latest_attempt.self_rating,
            "self_rating_label": SELF_RATING_LABELS.get(
                latest_attempt.self_rating,
                latest_attempt.self_rating,
            ),
            "score": latest_attempt.score,
            "is_correct": latest_attempt.is_correct,
            "answered_at": latest_attempt.answered_at,
        }

    weak_point_data = None

    if weak_point is not None:
        weak_point_data = {
            "id": weak_point.id,
            "weakness_score": weak_point.weakness_score,
            "wrong_count": weak_point.wrong_count,
            "partial_count": weak_point.partial_count,
            "correct_count": weak_point.correct_count,
            "status": weak_point.status,
            "last_answer": weak_point.last_answer,
            "updated_at": weak_point.updated_at,
        }

    return {
        "id": quiz.id,
        "document_id": quiz.document_id,
        "chapter_id": quiz.chapter_id,
        "question": quiz.question,
        "correct_answer": quiz.correct_answer,
        "explanation": quiz.explanation or "",
        "difficulty": quiz.difficulty,
        "attempt_count": attempt_count,
        "latest_attempt": latest_attempt_data,
        "weak_point": weak_point_data,
        "created_at": quiz.created_at,
        "updated_at": getattr(
            quiz,
            "updated_at",
            None,
        ),
    }


def _weak_point_to_dict(
    weak_point: WeakPoint,
    quiz: Optional[Quiz] = None,
    chapter: Optional[Chapter] = None,
    document: Optional[Document] = None,
) -> dict:
    """將 WeakPoint 轉成頁面可直接使用的字典。"""

    return {
        "id": weak_point.id,
        "document_id": weak_point.document_id,
        "document_name": (
            document.file_name
            if document is not None
            else ""
        ),
        "chapter_id": weak_point.chapter_id,
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
        "quiz_id": weak_point.quiz_id,
        "question": (
            quiz.question
            if quiz is not None
            else weak_point.title
        ),
        "title": weak_point.title,
        "source_type": weak_point.source_type,
        "weakness_score": weak_point.weakness_score,
        "wrong_count": weak_point.wrong_count,
        "partial_count": weak_point.partial_count,
        "correct_count": weak_point.correct_count,
        "last_answer": weak_point.last_answer or "",
        "correct_answer": weak_point.correct_answer or "",
        "explanation": weak_point.explanation or "",
        "status": weak_point.status,
        "created_at": weak_point.created_at,
        "updated_at": weak_point.updated_at,
    }


def _attempt_to_dict(
    attempt: QuizAttempt,
    quiz: Quiz,
    chapter: Optional[Chapter] = None,
    document: Optional[Document] = None,
) -> dict:
    """將 QuizAttempt 轉成頁面可直接使用的字典。"""

    return {
        "id": attempt.id,
        "quiz_id": attempt.quiz_id,
        "document_id": quiz.document_id,
        "document_name": (
            document.file_name
            if document is not None
            else ""
        ),
        "chapter_id": quiz.chapter_id,
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
        "question": quiz.question,
        "correct_answer": quiz.correct_answer,
        "explanation": quiz.explanation or "",
        "user_answer": attempt.user_answer,
        "self_rating": attempt.self_rating,
        "self_rating_label": SELF_RATING_LABELS.get(
            attempt.self_rating,
            attempt.self_rating,
        ),
        "score": attempt.score,
        "is_correct": attempt.is_correct,
        "answered_at": attempt.answered_at,
    }


def _get_quiz_or_raise(
    session,
    quiz_id: int | str,
) -> Quiz:
    """取得 Quiz；找不到時直接拋出錯誤。"""

    quiz = session.get(
        Quiz,
        quiz_id,
    )

    if quiz is None:
        raise ValueError(
            "找不到指定的 Quiz 題目。"
        )

    return quiz


def _calculate_weak_point_update(
    current_score: int,
    self_rating: str,
) -> tuple[int, str]:
    """
    計算新的弱點分數與狀態。

    規則：
    - 答錯：弱點分數 +2，狀態 active
    - 部分答對：弱點分數 +1
    - 答對：弱點分數 -1
    - 分數 <= 0：mastered
    - 尚未 mastered 且本次答對：improving
    - 部分答對且累積分數較低：improving
    - 其餘：active
    """

    current_score = max(
        _safe_int(current_score),
        0,
    )

    if self_rating == "wrong":
        return (
            current_score + 2,
            WEAK_POINT_ACTIVE,
        )

    if self_rating == "partial":
        new_score = current_score + 1

        if new_score <= 1:
            status = WEAK_POINT_IMPROVING
        else:
            status = WEAK_POINT_ACTIVE

        return new_score, status

    new_score = max(
        current_score - 1,
        0,
    )

    if new_score <= 0:
        return (
            0,
            WEAK_POINT_MASTERED,
        )

    return (
        new_score,
        WEAK_POINT_IMPROVING,
    )


def _update_weak_point_record(
    session,
    quiz: Quiz,
    user_answer: str,
    self_rating: str,
) -> Optional[WeakPoint]:
    """建立或更新單一 Quiz 對應的弱點紀錄。"""

    statement = select(
        WeakPoint
    ).where(
        WeakPoint.quiz_id == quiz.id
    )

    weak_point = session.execute(
        statement
    ).scalars().first()

    now = _utc_now()

    # 第一次就答對時，不建立弱點。
    if (
        weak_point is None
        and self_rating == "correct"
    ):
        return None

    if weak_point is None:
        weak_point = WeakPoint(
            document_id=quiz.document_id,
            chapter_id=quiz.chapter_id,
            quiz_id=quiz.id,
            title=quiz.question,
            source_type="quiz",
            weakness_score=0,
            wrong_count=0,
            partial_count=0,
            correct_count=0,
            last_answer=user_answer,
            correct_answer=quiz.correct_answer,
            explanation=quiz.explanation,
            status=WEAK_POINT_ACTIVE,
            created_at=now,
            updated_at=now,
        )

        session.add(
            weak_point
        )

    new_score, new_status = (
        _calculate_weak_point_update(
            current_score=(
                weak_point.weakness_score
            ),
            self_rating=self_rating,
        )
    )

    weak_point.document_id = (
        quiz.document_id
    )

    weak_point.chapter_id = (
        quiz.chapter_id
    )

    weak_point.title = quiz.question
    weak_point.source_type = "quiz"

    weak_point.weakness_score = (
        new_score
    )

    weak_point.last_answer = (
        user_answer
    )

    weak_point.correct_answer = (
        quiz.correct_answer
    )

    weak_point.explanation = (
        quiz.explanation
    )

    weak_point.status = new_status
    weak_point.updated_at = now

    if self_rating == "wrong":
        weak_point.wrong_count += 1

    elif self_rating == "partial":
        weak_point.partial_count += 1

    else:
        weak_point.correct_count += 1

    session.flush()

    return weak_point


def get_practice_documents() -> list[dict]:
    """
    取得可進行 Quiz 練習的文件。

    只回傳至少包含一題 Quiz 的文件。
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

        attempt_count_subquery = (
            select(
                Quiz.document_id.label(
                    "document_id"
                ),
                func.count(
                    QuizAttempt.id
                ).label(
                    "attempt_count"
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
            .where(
                WeakPoint.status
                != WEAK_POINT_MASTERED
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
                    attempt_count_subquery.c.attempt_count,
                    0,
                ).label(
                    "attempt_count"
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
                attempt_count_subquery,
                attempt_count_subquery.c.document_id
                == Document.id,
            )
            .outerjoin(
                weak_point_count_subquery,
                weak_point_count_subquery.c.document_id
                == Document.id,
            )
            .where(
                func.coalesce(
                    quiz_count_subquery.c.quiz_count,
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
                quiz_count=_safe_int(
                    quiz_count
                ),
                attempt_count=_safe_int(
                    attempt_count
                ),
                weak_point_count=_safe_int(
                    weak_point_count
                ),
            )
            for (
                document,
                chapter_count,
                quiz_count,
                attempt_count,
                weak_point_count,
            ) in rows
        ]


def get_chapters_by_document(
    document_id: int | str,
) -> list[dict]:
    """取得指定文件中具有 Quiz 的章節。"""

    with get_database_session() as session:
        quiz_count_subquery = (
            select(
                Quiz.chapter_id.label(
                    "chapter_id"
                ),
                func.count(
                    Quiz.id
                ).label(
                    "quiz_count"
                ),
            )
            .where(
                Quiz.document_id
                == document_id
            )
            .group_by(
                Quiz.chapter_id
            )
            .subquery()
        )

        attempt_count_subquery = (
            select(
                Quiz.chapter_id.label(
                    "chapter_id"
                ),
                func.count(
                    QuizAttempt.id
                ).label(
                    "attempt_count"
                ),
            )
            .join(
                QuizAttempt,
                QuizAttempt.quiz_id == Quiz.id,
            )
            .where(
                Quiz.document_id
                == document_id
            )
            .group_by(
                Quiz.chapter_id
            )
            .subquery()
        )

        weak_point_count_subquery = (
            select(
                WeakPoint.chapter_id.label(
                    "chapter_id"
                ),
                func.count(
                    WeakPoint.id
                ).label(
                    "weak_point_count"
                ),
            )
            .where(
                WeakPoint.document_id
                == document_id,
                WeakPoint.status
                != WEAK_POINT_MASTERED,
            )
            .group_by(
                WeakPoint.chapter_id
            )
            .subquery()
        )

        statement = (
            select(
                Chapter,
                func.coalesce(
                    quiz_count_subquery.c.quiz_count,
                    0,
                ).label(
                    "quiz_count"
                ),
                func.coalesce(
                    attempt_count_subquery.c.attempt_count,
                    0,
                ).label(
                    "attempt_count"
                ),
                func.coalesce(
                    weak_point_count_subquery.c.weak_point_count,
                    0,
                ).label(
                    "weak_point_count"
                ),
            )
            .outerjoin(
                quiz_count_subquery,
                quiz_count_subquery.c.chapter_id
                == Chapter.id,
            )
            .outerjoin(
                attempt_count_subquery,
                attempt_count_subquery.c.chapter_id
                == Chapter.id,
            )
            .outerjoin(
                weak_point_count_subquery,
                weak_point_count_subquery.c.chapter_id
                == Chapter.id,
            )
            .where(
                Chapter.document_id
                == document_id,
                func.coalesce(
                    quiz_count_subquery.c.quiz_count,
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
                quiz_count=_safe_int(
                    quiz_count
                ),
                attempt_count=_safe_int(
                    attempt_count
                ),
                weak_point_count=_safe_int(
                    weak_point_count
                ),
            )
            for (
                chapter,
                quiz_count,
                attempt_count,
                weak_point_count,
            ) in rows
        ]


def get_quizzes_by_chapter(
    document_id: int | str,
    chapter_id: int | str,
) -> list[dict]:
    """取得指定文件與章節的 Quiz。"""

    with get_database_session() as session:
        statement = (
            select(
                Quiz
            )
            .where(
                Quiz.document_id
                == document_id,
                Quiz.chapter_id
                == chapter_id,
            )
            .options(
                selectinload(
                    Quiz.attempts
                ),
                selectinload(
                    Quiz.weak_points
                ),
            )
            .order_by(
                Quiz.created_at.asc(),
                Quiz.id.asc(),
            )
        )

        quizzes = session.execute(
            statement
        ).scalars().unique().all()

        results = []

        for quiz in quizzes:
            attempts = sorted(
                quiz.attempts or [],
                key=lambda attempt: (
                    attempt.answered_at
                    or datetime.min
                ),
                reverse=True,
            )

            weak_points = (
                quiz.weak_points or []
            )

            weak_point = (
                weak_points[0]
                if weak_points
                else None
            )

            results.append(
                _quiz_to_dict(
                    quiz=quiz,
                    attempt_count=len(
                        attempts
                    ),
                    latest_attempt=(
                        attempts[0]
                        if attempts
                        else None
                    ),
                    weak_point=weak_point,
                )
            )

        return results


def get_quiz_by_id(
    quiz_id: int | str,
) -> Optional[dict]:
    """取得單一 Quiz 詳細資料。"""

    with get_database_session() as session:
        statement = (
            select(
                Quiz
            )
            .where(
                Quiz.id == quiz_id
            )
            .options(
                selectinload(
                    Quiz.attempts
                ),
                selectinload(
                    Quiz.weak_points
                ),
            )
        )

        quiz = session.execute(
            statement
        ).scalars().unique().first()

        if quiz is None:
            return None

        attempts = sorted(
            quiz.attempts or [],
            key=lambda attempt: (
                attempt.answered_at
                or datetime.min
            ),
            reverse=True,
        )

        weak_points = (
            quiz.weak_points or []
        )

        return _quiz_to_dict(
            quiz=quiz,
            attempt_count=len(
                attempts
            ),
            latest_attempt=(
                attempts[0]
                if attempts
                else None
            ),
            weak_point=(
                weak_points[0]
                if weak_points
                else None
            ),
        )


def save_quiz_attempt(
    quiz_id: int | str,
    user_answer: str,
    self_rating: str,
) -> dict:
    """
    儲存 Quiz 作答與自評結果。

    同一個交易中會：
    1. 寫入 quiz_attempts
    2. 建立或更新 weak_points
    """

    normalized_rating = (
        _normalize_self_rating(
            self_rating
        )
    )

    normalized_answer = _safe_text(
        user_answer
    ).strip()

    if not normalized_answer:
        raise ValueError(
            "請先輸入你的答案。"
        )

    score = SELF_RATING_SCORES[
        normalized_rating
    ]

    is_correct = (
        normalized_rating == "correct"
    )

    with get_database_session() as session:
        quiz = _get_quiz_or_raise(
            session=session,
            quiz_id=quiz_id,
        )

        attempt = QuizAttempt(
            quiz_id=quiz.id,
            user_answer=normalized_answer,
            self_rating=normalized_rating,
            score=score,
            is_correct=is_correct,
            answered_at=_utc_now(),
        )

        session.add(
            attempt
        )

        session.flush()

        weak_point = (
            _update_weak_point_record(
                session=session,
                quiz=quiz,
                user_answer=normalized_answer,
                self_rating=normalized_rating,
            )
        )

        session.commit()

        session.refresh(
            attempt
        )

        if weak_point is not None:
            session.refresh(
                weak_point
            )

        return {
            "saved": True,
            "attempt": {
                "id": attempt.id,
                "quiz_id": attempt.quiz_id,
                "user_answer": attempt.user_answer,
                "self_rating": attempt.self_rating,
                "self_rating_label": (
                    SELF_RATING_LABELS[
                        attempt.self_rating
                    ]
                ),
                "score": attempt.score,
                "is_correct": attempt.is_correct,
                "answered_at": attempt.answered_at,
            },
            "quiz": {
                "id": quiz.id,
                "document_id": quiz.document_id,
                "chapter_id": quiz.chapter_id,
                "question": quiz.question,
                "correct_answer": quiz.correct_answer,
                "explanation": quiz.explanation or "",
            },
            "weak_point": (
                {
                    "id": weak_point.id,
                    "weakness_score": (
                        weak_point.weakness_score
                    ),
                    "wrong_count": (
                        weak_point.wrong_count
                    ),
                    "partial_count": (
                        weak_point.partial_count
                    ),
                    "correct_count": (
                        weak_point.correct_count
                    ),
                    "status": weak_point.status,
                }
                if weak_point is not None
                else None
            ),
        }


def update_weak_point_from_attempt(
    quiz_id: int | str,
    user_answer: str,
    self_rating: str,
) -> dict:
    """
    單獨建立或更新弱點紀錄。

    一般情況應直接使用 save_quiz_attempt()，
    因為它會同時寫入作答紀錄與更新弱點。
    """

    normalized_rating = (
        _normalize_self_rating(
            self_rating
        )
    )

    normalized_answer = _safe_text(
        user_answer
    ).strip()

    with get_database_session() as session:
        quiz = _get_quiz_or_raise(
            session=session,
            quiz_id=quiz_id,
        )

        weak_point = (
            _update_weak_point_record(
                session=session,
                quiz=quiz,
                user_answer=normalized_answer,
                self_rating=normalized_rating,
            )
        )

        session.commit()

        if weak_point is None:
            return {
                "updated": True,
                "weak_point": None,
                "reason": (
                    "第一次作答即答對，"
                    "不建立弱點紀錄。"
                ),
            }

        session.refresh(
            weak_point
        )

        return {
            "updated": True,
            "reason": "",
            "weak_point": {
                "id": weak_point.id,
                "quiz_id": weak_point.quiz_id,
                "weakness_score": (
                    weak_point.weakness_score
                ),
                "wrong_count": (
                    weak_point.wrong_count
                ),
                "partial_count": (
                    weak_point.partial_count
                ),
                "correct_count": (
                    weak_point.correct_count
                ),
                "status": weak_point.status,
                "updated_at": weak_point.updated_at,
            },
        }


def get_wrong_questions(
    document_id: int | str,
    chapter_id: Optional[int | str] = None,
) -> list[dict]:
    """
    取得錯題本。

    條件：
    - 至少答錯或部分答對一次
    - 尚未 mastered
    """

    with get_database_session() as session:
        statement = (
            select(
                WeakPoint,
                Quiz,
                Chapter,
                Document,
            )
            .join(
                Quiz,
                WeakPoint.quiz_id == Quiz.id,
            )
            .outerjoin(
                Chapter,
                WeakPoint.chapter_id == Chapter.id,
            )
            .join(
                Document,
                WeakPoint.document_id == Document.id,
            )
            .where(
                WeakPoint.document_id
                == document_id,
                WeakPoint.status
                != WEAK_POINT_MASTERED,
                (
                    WeakPoint.wrong_count
                    + WeakPoint.partial_count
                )
                > 0,
            )
        )

        if chapter_id is not None:
            statement = statement.where(
                WeakPoint.chapter_id
                == chapter_id
            )

        statement = statement.order_by(
            WeakPoint.weakness_score.desc(),
            WeakPoint.wrong_count.desc(),
            WeakPoint.partial_count.desc(),
            WeakPoint.updated_at.desc(),
        )

        rows = session.execute(
            statement
        ).all()

        return [
            _weak_point_to_dict(
                weak_point=weak_point,
                quiz=quiz,
                chapter=chapter,
                document=document,
            )
            for (
                weak_point,
                quiz,
                chapter,
                document,
            ) in rows
        ]


def get_weak_points(
    document_id: int | str,
    chapter_id: Optional[int | str] = None,
    statuses: Optional[Iterable[str]] = None,
) -> list[dict]:
    """
    取得不熟重點。

    預設回傳 active 與 improving。
    若傳入 statuses，可指定包含 mastered。
    """

    normalized_statuses = (
        _normalize_statuses(
            statuses
        )
    )

    if not normalized_statuses:
        normalized_statuses = [
            WEAK_POINT_ACTIVE,
            WEAK_POINT_IMPROVING,
        ]

    with get_database_session() as session:
        statement = (
            select(
                WeakPoint,
                Quiz,
                Chapter,
                Document,
            )
            .join(
                Quiz,
                WeakPoint.quiz_id == Quiz.id,
            )
            .outerjoin(
                Chapter,
                WeakPoint.chapter_id == Chapter.id,
            )
            .join(
                Document,
                WeakPoint.document_id == Document.id,
            )
            .where(
                WeakPoint.document_id
                == document_id,
                WeakPoint.status.in_(
                    normalized_statuses
                ),
            )
        )

        if chapter_id is not None:
            statement = statement.where(
                WeakPoint.chapter_id
                == chapter_id
            )

        statement = statement.order_by(
            WeakPoint.weakness_score.desc(),
            WeakPoint.updated_at.desc(),
        )

        rows = session.execute(
            statement
        ).all()

        return [
            _weak_point_to_dict(
                weak_point=weak_point,
                quiz=quiz,
                chapter=chapter,
                document=document,
            )
            for (
                weak_point,
                quiz,
                chapter,
                document,
            ) in rows
        ]


def get_quiz_attempt_history(
    document_id: int | str,
    chapter_id: Optional[int | str] = None,
    limit: int = 100,
) -> list[dict]:
    """取得 Quiz 練習紀錄。"""

    safe_limit = max(
        min(
            _safe_int(limit, 100),
            500,
        ),
        1,
    )

    with get_database_session() as session:
        statement = (
            select(
                QuizAttempt,
                Quiz,
                Chapter,
                Document,
            )
            .join(
                Quiz,
                QuizAttempt.quiz_id == Quiz.id,
            )
            .outerjoin(
                Chapter,
                Quiz.chapter_id == Chapter.id,
            )
            .join(
                Document,
                Quiz.document_id == Document.id,
            )
            .where(
                Quiz.document_id
                == document_id
            )
        )

        if chapter_id is not None:
            statement = statement.where(
                Quiz.chapter_id
                == chapter_id
            )

        statement = (
            statement
            .order_by(
                QuizAttempt.answered_at.desc()
            )
            .limit(
                safe_limit
            )
        )

        rows = session.execute(
            statement
        ).all()

        return [
            _attempt_to_dict(
                attempt=attempt,
                quiz=quiz,
                chapter=chapter,
                document=document,
            )
            for (
                attempt,
                quiz,
                chapter,
                document,
            ) in rows
        ]


def get_practice_summary(
    document_id: int | str,
    chapter_id: Optional[int | str] = None,
) -> dict:
    """取得文件或章節的 Quiz 練習統計。"""

    with get_database_session() as session:
        quiz_filters = [
            Quiz.document_id == document_id
        ]

        if chapter_id is not None:
            quiz_filters.append(
                Quiz.chapter_id == chapter_id
            )

        quiz_count = (
            session.query(
                func.count(
                    Quiz.id
                )
            )
            .filter(
                *quiz_filters
            )
            .scalar()
            or 0
        )

        attempt_query = (
            session.query(
                QuizAttempt.self_rating,
                func.count(
                    QuizAttempt.id
                ),
            )
            .join(
                Quiz,
                QuizAttempt.quiz_id == Quiz.id,
            )
            .filter(
                *quiz_filters
            )
            .group_by(
                QuizAttempt.self_rating
            )
        )

        rating_counts = {
            "correct": 0,
            "partial": 0,
            "wrong": 0,
        }

        for rating, count in attempt_query.all():
            normalized_rating = (
                SELF_RATING_ALIASES.get(
                    _safe_text(
                        rating
                    ).strip().lower(),
                    _safe_text(
                        rating
                    ).strip().lower(),
                )
            )

            if normalized_rating in rating_counts:
                rating_counts[
                    normalized_rating
                ] = _safe_int(
                    count
                )

        attempt_count = sum(
            rating_counts.values()
        )

        total_score = (
            rating_counts["correct"] * 2
            + rating_counts["partial"]
        )

        max_score = attempt_count * 2

        score_rate = (
            round(
                total_score
                / max_score
                * 100,
                1,
            )
            if max_score > 0
            else 0.0
        )

        weak_point_filters = [
            WeakPoint.document_id
            == document_id
        ]

        if chapter_id is not None:
            weak_point_filters.append(
                WeakPoint.chapter_id
                == chapter_id
            )

        weak_point_rows = (
            session.query(
                WeakPoint.status,
                func.count(
                    WeakPoint.id
                ),
            )
            .filter(
                *weak_point_filters
            )
            .group_by(
                WeakPoint.status
            )
            .all()
        )

        weak_point_counts = {
            WEAK_POINT_ACTIVE: 0,
            WEAK_POINT_IMPROVING: 0,
            WEAK_POINT_MASTERED: 0,
        }

        for status, count in weak_point_rows:
            if status in weak_point_counts:
                weak_point_counts[
                    status
                ] = _safe_int(
                    count
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
            "quiz_count": _safe_int(
                quiz_count
            ),
            "attempt_count": attempt_count,
            "correct_count": (
                rating_counts["correct"]
            ),
            "partial_count": (
                rating_counts["partial"]
            ),
            "wrong_count": (
                rating_counts["wrong"]
            ),
            "total_score": total_score,
            "max_score": max_score,
            "score_rate": score_rate,
            "active_weak_point_count": (
                weak_point_counts[
                    WEAK_POINT_ACTIVE
                ]
            ),
            "improving_weak_point_count": (
                weak_point_counts[
                    WEAK_POINT_IMPROVING
                ]
            ),
            "mastered_weak_point_count": (
                weak_point_counts[
                    WEAK_POINT_MASTERED
                ]
            ),
        }
