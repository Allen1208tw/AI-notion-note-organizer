from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from typing import Any


def get_item_value(item: Any, name: str, default: Any = "") -> Any:
    """Read a field from either a Pydantic object or a dictionary."""

    if isinstance(item, dict):
        return item.get(name, default)

    return getattr(item, name, default)


def get_learning_items(chapter_note: Any, *names: str) -> list[Any]:
    """Return the first available Quiz or Flash Card collection."""

    for name in names:
        value = get_item_value(chapter_note, name, None)

        if value is None or isinstance(value, (str, bytes, dict)):
            continue

        if isinstance(value, Iterable):
            return list(value)

    return []


def normalize_learning_text(value: Any) -> str:
    """Normalize learning text so harmless formatting changes compare equal."""

    text = unicodedata.normalize("NFKC", str(value or "")).strip().casefold()
    punctuation_map = str.maketrans(
        {
            "，": ",",
            "。": ".",
            "：": ":",
            "；": ";",
            "？": "?",
            "！": "!",
            "、": ",",
            "“": '"',
            "”": '"',
            "‘": "'",
            "’": "'",
        }
    )
    text = text.translate(punctuation_map)
    text = re.sub(r"\s+", "", text)
    text = re.sub(r"[`'\"()\[\]{}<>.,:;!?，。；：！？、]", "", text)

    return text


def quiz_identity(question: Any, answer: Any) -> str:
    """Build a stable identity for a Quiz in one chapter."""

    return f"{normalize_learning_text(question)}|{normalize_learning_text(answer)}"


def flashcard_identity(front: Any, back: Any) -> str:
    """Build a stable identity for a Flash Card in one chapter."""

    return f"{normalize_learning_text(front)}|{normalize_learning_text(back)}"


def prepare_unique_quizzes(chapter_note: Any) -> tuple[list[dict], int]:
    """Validate and deduplicate Quiz items inside one generated note."""

    unique_items: list[dict] = []
    seen: set[str] = set()
    skipped_count = 0

    for item in get_learning_items(chapter_note, "quiz", "quizzes"):
        question = str(get_item_value(item, "question", "") or "").strip()
        answer = str(
            get_item_value(
                item,
                "answer",
                get_item_value(item, "correct_answer", ""),
            )
            or ""
        ).strip()
        explanation = str(get_item_value(item, "explanation", "") or "").strip()
        difficulty = str(get_item_value(item, "difficulty", "medium") or "medium").strip()
        identity = quiz_identity(question, answer)

        if not question or not answer or not identity.replace("|", ""):
            skipped_count += 1
            continue

        if identity in seen:
            skipped_count += 1
            continue

        seen.add(identity)
        unique_items.append(
            {
                "question": question,
                "answer": answer,
                "explanation": explanation,
                "difficulty": difficulty or "medium",
                "identity": identity,
            }
        )

    return unique_items, skipped_count


def prepare_unique_flashcards(chapter_note: Any) -> tuple[list[dict], int]:
    """Validate and deduplicate Flash Cards inside one generated note."""

    unique_items: list[dict] = []
    seen: set[str] = set()
    skipped_count = 0

    for item in get_learning_items(chapter_note, "flashcards", "flash_cards"):
        front = str(get_item_value(item, "front", "") or "").strip()
        back = str(get_item_value(item, "back", "") or "").strip()
        identity = flashcard_identity(front, back)

        if not front or not back or not identity.replace("|", ""):
            skipped_count += 1
            continue

        if identity in seen:
            skipped_count += 1
            continue

        seen.add(identity)
        unique_items.append(
            {
                "front": front,
                "back": back,
                "identity": identity,
            }
        )

    return unique_items, skipped_count
