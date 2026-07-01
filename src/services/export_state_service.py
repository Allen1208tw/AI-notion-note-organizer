from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from src.config.settings import OUTPUT_DIR


EXPORT_JOBS_DIR = OUTPUT_DIR / "export_jobs"


def _safe_file_name(file_name: str) -> str:
    """
    將檔名轉成適合 Windows 與 JSON 檔案使用的名稱。
    """

    stem = Path(file_name).stem.strip()

    if not stem:
        stem = "untitled_document"

    safe_name = re.sub(r'[\\/:*?"<>|]+', "_", stem)
    safe_name = re.sub(r"\s+", "_", safe_name)

    return safe_name[:100]


def get_export_state_path(document_name: str) -> Path:
    """
    取得指定文件的匯出進度 JSON 路徑。
    """

    safe_name = _safe_file_name(document_name)

    return (
        EXPORT_JOBS_DIR
        / f"{safe_name}_detailed_notion_export_state.json"
    )


def _default_state(
    document_name: str,
    chapter_count: int,
) -> dict[str, Any]:
    """
    建立新的匯出進度資料結構。
    """

    now = datetime.now().isoformat(timespec="seconds")

    return {
        "document_name": document_name,
        "chapter_count": chapter_count,
        "parent_page_id": "",
        "parent_page_url": "",
        "completed_chapters": {},
        "failed_chapters": {},
        "created_at": now,
        "updated_at": now,
        "is_finished": False,
    }


def save_export_state(
    document_name: str,
    state: dict[str, Any],
) -> Path:
    """
    將目前進度寫入 JSON。

    每完成或失敗一個章節都應呼叫一次。
    """

    EXPORT_JOBS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    state["updated_at"] = datetime.now().isoformat(
        timespec="seconds"
    )

    state_path = get_export_state_path(document_name)

    with state_path.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            state,
            file,
            ensure_ascii=False,
            indent=4,
        )

    return state_path


def load_export_state(
    document_name: str,
    chapter_count: int,
) -> dict[str, Any]:
    """
    讀取既有匯出進度。

    找不到檔案、檔案壞掉或文件章節數不同時，
    會安全地建立新的進度資料。
    """

    state_path = get_export_state_path(document_name)

    if not state_path.exists():
        state = _default_state(
            document_name=document_name,
            chapter_count=chapter_count,
        )

        save_export_state(
            document_name=document_name,
            state=state,
        )

        return state

    try:
        with state_path.open(
            "r",
            encoding="utf-8",
        ) as file:
            state = json.load(file)

    except (json.JSONDecodeError, OSError):
        state = _default_state(
            document_name=document_name,
            chapter_count=chapter_count,
        )

        save_export_state(
            document_name=document_name,
            state=state,
        )

        return state

    saved_document_name = state.get("document_name", "")
    saved_chapter_count = state.get("chapter_count", 0)

    if (
        saved_document_name != document_name
        or saved_chapter_count != chapter_count
    ):
        state = _default_state(
            document_name=document_name,
            chapter_count=chapter_count,
        )

        save_export_state(
            document_name=document_name,
            state=state,
        )

        return state

    state.setdefault("parent_page_id", "")
    state.setdefault("parent_page_url", "")
    state.setdefault("completed_chapters", {})
    state.setdefault("failed_chapters", {})
    state.setdefault("is_finished", False)

    return state


def reset_export_state(
    document_name: str,
    chapter_count: int,
) -> dict[str, Any]:
    """
    清除舊進度，建立新的匯出工作。
    """

    state = _default_state(
        document_name=document_name,
        chapter_count=chapter_count,
    )

    save_export_state(
        document_name=document_name,
        state=state,
    )

    return state


def set_parent_page(
    document_name: str,
    state: dict[str, Any],
    parent_page_id: str,
    parent_page_url: str,
) -> dict[str, Any]:
    """
    保存 Notion 父頁資訊。
    """

    state["parent_page_id"] = parent_page_id
    state["parent_page_url"] = parent_page_url

    save_export_state(
        document_name=document_name,
        state=state,
    )

    return state


def mark_chapter_completed(
    document_name: str,
    state: dict[str, Any],
    chapter_id: str | int,
    chapter_title: str,
    notion_url: str,
) -> dict[str, Any]:
    """
    記錄某個 Module 已成功建立。
    """

    chapter_key = str(chapter_id)

    state["completed_chapters"][chapter_key] = {
        "chapter_title": chapter_title,
        "notion_url": notion_url,
        "completed_at": datetime.now().isoformat(
            timespec="seconds"
        ),
    }

    state["failed_chapters"].pop(chapter_key, None)

    save_export_state(
        document_name=document_name,
        state=state,
    )

    return state


def mark_chapter_failed(
    document_name: str,
    state: dict[str, Any],
    chapter_id: str | int,
    chapter_title: str,
    error_message: str,
) -> dict[str, Any]:
    """
    記錄某個 Module 匯出失敗。
    """

    chapter_key = str(chapter_id)

    state["failed_chapters"][chapter_key] = {
        "chapter_title": chapter_title,
        "error": error_message,
        "failed_at": datetime.now().isoformat(
            timespec="seconds"
        ),
    }

    save_export_state(
        document_name=document_name,
        state=state,
    )

    return state


def is_chapter_completed(
    state: dict[str, Any],
    chapter_id: str | int,
) -> bool:
    """
    判斷某個 Module 是否已成功匯出。
    """

    chapter_key = str(chapter_id)

    return chapter_key in state.get(
        "completed_chapters",
        {},
    )


def get_pending_chapters(
    chapters: list[dict],
    state: dict[str, Any],
) -> list[dict]:
    """
    回傳尚未完成的章節。

    已完成的 Module 會自動跳過。
    """

    pending_chapters = []

    for chapter in chapters:
        chapter_id = chapter.get("chapter_id")

        if not is_chapter_completed(
            state=state,
            chapter_id=chapter_id,
        ):
            pending_chapters.append(chapter)

    return pending_chapters


def mark_export_finished(
    document_name: str,
    state: dict[str, Any],
) -> dict[str, Any]:
    """
    標示整份文件匯出完成。
    """

    state["is_finished"] = True

    save_export_state(
        document_name=document_name,
        state=state,
    )

    return state