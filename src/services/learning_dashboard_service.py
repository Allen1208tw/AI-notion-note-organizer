from __future__ import annotations

from datetime import datetime
from typing import Optional

from src.services.flashcard_practice_service import (
    get_flashcard_documents,
    get_flashcard_review_history,
    get_flashcard_summary,
)
from src.services.quiz_practice_service import (
    get_practice_documents,
    get_practice_summary,
    get_quiz_attempt_history,
    get_weak_points,
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


def _safe_float(value, default: float = 0.0) -> float:
    """安全轉換為浮點數。"""

    try:
        if value is None:
            return default

        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_datetime(value) -> Optional[datetime]:
    """安全轉換為 datetime。"""

    if value is None:
        return None

    if isinstance(value, datetime):
        return value

    text = _safe_text(value).strip()

    if not text:
        return None

    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _merge_document_record(
    current: dict,
    incoming: dict,
) -> dict:
    """合併 Quiz 與 Flash Card 文件資訊。"""

    merged = dict(current)

    for key, value in incoming.items():
        if key not in merged or merged.get(key) in (
            None,
            "",
            0,
        ):
            merged[key] = value

    return merged


def get_learning_documents() -> list[dict]:
    """
    取得所有具有 Quiz 或 Flash Cards 的文件。

    同一份文件只回傳一次。
    """

    quiz_documents = get_practice_documents()
    flashcard_documents = get_flashcard_documents()

    document_map: dict[str, dict] = {}

    for document in quiz_documents:
        document_id = _safe_text(
            document.get("id")
        )

        if not document_id:
            continue

        document_map[document_id] = {
            "id": document.get("id"),
            "file_name": document.get(
                "file_name",
                "未命名文件",
            ),
            "file_extension": document.get(
                "file_extension",
                "",
            ),
            "chapter_count": _safe_int(
                document.get("chapter_count")
            ),
            "quiz_count": _safe_int(
                document.get("quiz_count")
            ),
            "quiz_attempt_count": _safe_int(
                document.get("attempt_count")
            ),
            "weak_point_count": _safe_int(
                document.get(
                    "weak_point_count"
                )
            ),
            "flashcard_count": 0,
            "flashcard_review_count": 0,
            "flashcard_due_count": 0,
            "created_at": document.get(
                "created_at"
            ),
            "updated_at": document.get(
                "updated_at"
            ),
        }

    for document in flashcard_documents:
        document_id = _safe_text(
            document.get("id")
        )

        if not document_id:
            continue

        incoming = {
            "id": document.get("id"),
            "file_name": document.get(
                "file_name",
                "未命名文件",
            ),
            "file_extension": document.get(
                "file_extension",
                "",
            ),
            "chapter_count": _safe_int(
                document.get("chapter_count")
            ),
            "quiz_count": 0,
            "quiz_attempt_count": 0,
            "weak_point_count": 0,
            "flashcard_count": _safe_int(
                document.get(
                    "flashcard_count"
                )
            ),
            "flashcard_review_count": (
                _safe_int(
                    document.get(
                        "review_count"
                    )
                )
            ),
            "flashcard_due_count": _safe_int(
                document.get("due_count")
            ),
            "created_at": document.get(
                "created_at"
            ),
            "updated_at": document.get(
                "updated_at"
            ),
        }

        if document_id in document_map:
            existing = document_map[
                document_id
            ]

            existing[
                "flashcard_count"
            ] = incoming[
                "flashcard_count"
            ]

            existing[
                "flashcard_review_count"
            ] = incoming[
                "flashcard_review_count"
            ]

            existing[
                "flashcard_due_count"
            ] = incoming[
                "flashcard_due_count"
            ]

            existing[
                "chapter_count"
            ] = max(
                _safe_int(
                    existing.get(
                        "chapter_count"
                    )
                ),
                _safe_int(
                    incoming.get(
                        "chapter_count"
                    )
                ),
            )

            document_map[
                document_id
            ] = _merge_document_record(
                existing,
                incoming,
            )

        else:
            document_map[
                document_id
            ] = incoming

    documents = list(
        document_map.values()
    )

    documents.sort(
        key=lambda item: (
            _safe_datetime(
                item.get("updated_at")
            )
            or datetime.min
        ),
        reverse=True,
    )

    return documents


def get_document_learning_overview(
    document_id: int | str,
) -> dict:
    """取得單一文件的完整學習概況。"""

    quiz_summary = get_practice_summary(
        document_id=document_id
    )

    flashcard_summary = (
        get_flashcard_summary(
            document_id=document_id
        )
    )

    weak_points = get_weak_points(
        document_id=document_id,
        statuses=[
            "active",
            "improving",
        ],
    )

    active_weak_points = [
        item
        for item in weak_points
        if item.get("status") == "active"
    ]

    improving_weak_points = [
        item
        for item in weak_points
        if item.get("status")
        == "improving"
    ]

    quiz_attempt_count = _safe_int(
        quiz_summary.get("attempt_count")
    )

    correct_count = _safe_int(
        quiz_summary.get("correct_count")
    )

    quiz_accuracy = (
        round(
            correct_count
            / quiz_attempt_count
            * 100,
            1,
        )
        if quiz_attempt_count > 0
        else 0.0
    )

    flashcard_count = _safe_int(
        flashcard_summary.get(
            "flashcard_count"
        )
    )

    reviewed_flashcard_count = _safe_int(
        flashcard_summary.get(
            "reviewed_flashcard_count"
        )
    )

    flashcard_completion_rate = (
        round(
            reviewed_flashcard_count
            / flashcard_count
            * 100,
            1,
        )
        if flashcard_count > 0
        else 0.0
    )

    return {
        "document_id": _safe_text(
            document_id
        ),
        "quiz": {
            **quiz_summary,
            "accuracy": quiz_accuracy,
        },
        "flashcard": {
            **flashcard_summary,
            "completion_rate": (
                flashcard_completion_rate
            ),
        },
        "weak_points": {
            "total_count": len(
                weak_points
            ),
            "active_count": len(
                active_weak_points
            ),
            "improving_count": len(
                improving_weak_points
            ),
            "items": weak_points,
        },
    }


def get_recent_learning_activity(
    document_id: int | str,
    limit_each: int = 10,
) -> list[dict]:
    """
    取得最近 Quiz 與 Flash Card 活動。

    兩種活動會依時間混合排序。
    """

    safe_limit = max(
        min(
            _safe_int(
                limit_each,
                10,
            ),
            100,
        ),
        1,
    )

    quiz_history = get_quiz_attempt_history(
        document_id=document_id,
        limit=safe_limit,
    )

    flashcard_history = (
        get_flashcard_review_history(
            document_id=document_id,
            limit=safe_limit,
        )
    )

    activities: list[dict] = []

    for item in quiz_history:
        activities.append(
            {
                "activity_type": "quiz",
                "activity_label": "Quiz 作答",
                "title": item.get(
                    "question",
                    "未命名 Quiz",
                ),
                "chapter_title": item.get(
                    "chapter_title",
                    "",
                ),
                "result": item.get(
                    "self_rating_label",
                    "",
                ),
                "score": item.get(
                    "score",
                    0,
                ),
                "max_score": 2,
                "occurred_at": item.get(
                    "answered_at"
                ),
                "raw": item,
            }
        )

    for item in flashcard_history:
        activities.append(
            {
                "activity_type": "flashcard",
                "activity_label": (
                    "Flash Card 複習"
                ),
                "title": item.get(
                    "front",
                    "未命名 Flash Card",
                ),
                "chapter_title": item.get(
                    "chapter_title",
                    "",
                ),
                "result": item.get(
                    "familiarity_label",
                    "",
                ),
                "score": item.get(
                    "familiarity_score",
                    0,
                ),
                "max_score": 5,
                "occurred_at": item.get(
                    "reviewed_at"
                ),
                "raw": item,
            }
        )

    activities.sort(
        key=lambda item: (
            _safe_datetime(
                item.get("occurred_at")
            )
            or datetime.min
        ),
        reverse=True,
    )

    return activities[
        : safe_limit * 2
    ]


def get_learning_dashboard_data(
    document_id: int | str,
    activity_limit: int = 10,
) -> dict:
    """一次取得儀表板所需全部資料。"""

    overview = (
        get_document_learning_overview(
            document_id=document_id
        )
    )

    recent_activity = (
        get_recent_learning_activity(
            document_id=document_id,
            limit_each=activity_limit,
        )
    )

    quiz = overview.get(
        "quiz",
        {},
    )

    flashcard = overview.get(
        "flashcard",
        {},
    )

    weak_points = overview.get(
        "weak_points",
        {},
    )

    total_learning_actions = (
        _safe_int(
            quiz.get("attempt_count")
        )
        + _safe_int(
            flashcard.get("review_count")
        )
    )

    learning_health_score = 0.0

    score_parts = []

    if _safe_int(
        quiz.get("attempt_count")
    ) > 0:
        score_parts.append(
            _safe_float(
                quiz.get("score_rate")
            )
        )

    if _safe_int(
        flashcard.get("review_count")
    ) > 0:
        score_parts.append(
            _safe_float(
                flashcard.get(
                    "average_familiarity_score"
                )
            )
            / 5
            * 100
        )

    if score_parts:
        learning_health_score = round(
            sum(score_parts)
            / len(score_parts),
            1,
        )

    return {
        "document_id": _safe_text(
            document_id
        ),
        "overview": overview,
        "recent_activity": recent_activity,
        "total_learning_actions": (
            total_learning_actions
        ),
        "learning_health_score": (
            learning_health_score
        ),
        "priority_review_count": (
            _safe_int(
                weak_points.get(
                    "active_count"
                )
            )
            + _safe_int(
                flashcard.get(
                    "due_count"
                )
            )
        ),
    }
