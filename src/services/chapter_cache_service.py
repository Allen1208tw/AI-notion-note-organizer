from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from src.config.settings import OUTPUT_DIR
from src.models.chapter_models import ChapterLearningNote


CACHE_VERSION = "1.0"
CHAPTER_CACHE_DIR = OUTPUT_DIR / "chapter_cache"


def _safe_file_name(file_name: str) -> str:
    """
    將檔名轉成適合 Windows 資料夾與 JSON 檔使用的名稱。
    """

    stem = Path(file_name).stem.strip()

    if not stem:
        stem = "untitled_document"

    safe_name = re.sub(r'[\\/:*?"<>|]+', "_", stem)
    safe_name = re.sub(r"\s+", "_", safe_name)

    return safe_name[:100]


def _chapter_content_hash(chapter: dict) -> str:
    """
    根據章節內容建立短雜湊值。

    只要同一 Module 的內容改變，
    就會自動使用新的快取檔，避免讀到過期資料。
    """

    source_text = "\n".join(
        [
            str(chapter.get("chapter_id", "")),
            str(chapter.get("title", "")),
            str(chapter.get("content", "")),
        ]
    )

    return hashlib.sha256(
        source_text.encode("utf-8")
    ).hexdigest()[:16]


def get_document_cache_dir(document_name: str) -> Path:
    """
    取得指定文件專屬的快取資料夾。
    """

    safe_name = _safe_file_name(document_name)

    return CHAPTER_CACHE_DIR / safe_name


def get_chapter_cache_path(
    document_name: str,
    chapter: dict,
) -> Path:
    """
    取得指定 Module 的快取 JSON 路徑。
    """

    chapter_id = str(chapter.get("chapter_id", "unknown"))
    content_hash = _chapter_content_hash(chapter)

    safe_chapter_id = re.sub(
        r'[\\/:*?"<>|]+',
        "_",
        chapter_id,
    )

    file_name = (
        f"chapter_{safe_chapter_id}_"
        f"{content_hash}.json"
    )

    return get_document_cache_dir(document_name) / file_name


def _default_cache_data(
    document_name: str,
    chapter: dict,
) -> dict[str, Any]:
    """
    建立新的章節快取資料格式。
    """

    now = datetime.now().isoformat(timespec="seconds")

    return {
        "cache_version": CACHE_VERSION,
        "document_name": document_name,
        "chapter_id": str(chapter.get("chapter_id", "")),
        "chapter_title": str(chapter.get("title", "")),
        "content_hash": _chapter_content_hash(chapter),
        "visual_analysis_completed": False,
        "visual_context": [],
        "chapter_note_completed": False,
        "chapter_note": None,
        "created_at": now,
        "updated_at": now,
    }


def _sanitize_visual_context(
    visual_context: list[dict],
) -> list[dict]:
    """
    移除 Base64 圖片資料後再存入快取。

    image_data_url 很大，而且 Notion 匯出只需要圖片文字解讀，
    不需要把圖片 Base64 重複寫進 JSON。
    """

    sanitized_context = []

    for item in visual_context:
        if not isinstance(item, dict):
            continue

        cleaned_item = {
            key: value
            for key, value in item.items()
            if key != "image_data_url"
        }

        sanitized_context.append(cleaned_item)

    return sanitized_context


def load_chapter_cache(
    document_name: str,
    chapter: dict,
) -> dict[str, Any]:
    """
    讀取單一 Module 快取。

    回傳：
    {
        "visual_context": list[dict],
        "visual_cached": bool,
        "chapter_note": ChapterLearningNote | None,
        "note_cached": bool,
        "cache_path": Path,
    }
    """

    cache_path = get_chapter_cache_path(
        document_name=document_name,
        chapter=chapter,
    )

    empty_result = {
        "visual_context": [],
        "visual_cached": False,
        "chapter_note": None,
        "note_cached": False,
        "cache_path": cache_path,
    }

    if not cache_path.exists():
        return empty_result

    try:
        with cache_path.open(
            "r",
            encoding="utf-8",
        ) as file:
            cache_data = json.load(file)

    except (json.JSONDecodeError, OSError):
        return empty_result

    if cache_data.get("cache_version") != CACHE_VERSION:
        return empty_result

    if cache_data.get("document_name") != document_name:
        return empty_result

    if cache_data.get("content_hash") != _chapter_content_hash(chapter):
        return empty_result

    visual_cached = bool(
        cache_data.get("visual_analysis_completed", False)
    )

    visual_context = cache_data.get("visual_context", [])

    if not isinstance(visual_context, list):
        visual_context = []

    note_cached = bool(
        cache_data.get("chapter_note_completed", False)
    )

    chapter_note = None

    if note_cached and cache_data.get("chapter_note"):
        try:
            chapter_note = ChapterLearningNote.model_validate(
                cache_data["chapter_note"]
            )
        except Exception:
            note_cached = False
            chapter_note = None

    return {
        "visual_context": visual_context,
        "visual_cached": visual_cached,
        "chapter_note": chapter_note,
        "note_cached": note_cached,
        "cache_path": cache_path,
    }


def _load_or_create_cache_data(
    document_name: str,
    chapter: dict,
) -> tuple[dict[str, Any], Path]:
    """
    讀取既有快取資料；沒有或格式不符時建立新資料。
    """

    cache_path = get_chapter_cache_path(
        document_name=document_name,
        chapter=chapter,
    )

    default_data = _default_cache_data(
        document_name=document_name,
        chapter=chapter,
    )

    if not cache_path.exists():
        return default_data, cache_path

    try:
        with cache_path.open(
            "r",
            encoding="utf-8",
        ) as file:
            cache_data = json.load(file)

    except (json.JSONDecodeError, OSError):
        return default_data, cache_path

    if cache_data.get("cache_version") != CACHE_VERSION:
        return default_data, cache_path

    if cache_data.get("document_name") != document_name:
        return default_data, cache_path

    if cache_data.get("content_hash") != _chapter_content_hash(chapter):
        return default_data, cache_path

    return cache_data, cache_path


def _save_cache_data(
    cache_path: Path,
    cache_data: dict[str, Any],
) -> Path:
    """
    寫入快取 JSON。
    """

    cache_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    cache_data["updated_at"] = datetime.now().isoformat(
        timespec="seconds"
    )

    with cache_path.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            cache_data,
            file,
            ensure_ascii=False,
            indent=4,
        )

    return cache_path


def save_visual_context_cache(
    document_name: str,
    chapter: dict,
    visual_context: list[dict],
) -> Path:
    """
    在 PDF 視覺分析完成後立刻保存結果。
    """

    cache_data, cache_path = _load_or_create_cache_data(
        document_name=document_name,
        chapter=chapter,
    )

    cache_data["visual_analysis_completed"] = True
    cache_data["visual_context"] = _sanitize_visual_context(
        visual_context
    )

    return _save_cache_data(
        cache_path=cache_path,
        cache_data=cache_data,
    )


def save_chapter_note_cache(
    document_name: str,
    chapter: dict,
    chapter_note: ChapterLearningNote,
) -> Path:
    """
    在 AI 詳細筆記生成完成後立刻保存結果。

    即使後續 Notion API 寫入失敗，
    也能在下次續跑時直接讀取這份筆記。
    """

    cache_data, cache_path = _load_or_create_cache_data(
        document_name=document_name,
        chapter=chapter,
    )

    cache_data["chapter_note_completed"] = True
    cache_data["chapter_note"] = chapter_note.model_dump(
        mode="json"
    )

    return _save_cache_data(
        cache_path=cache_path,
        cache_data=cache_data,
    )


def clear_document_cache(document_name: str) -> int:
    """
    清除指定文件的所有 Module 快取。

    回傳實際刪除的 JSON 檔數量。
    """

    document_cache_dir = get_document_cache_dir(document_name)

    if not document_cache_dir.exists():
        return 0

    deleted_count = 0

    for cache_file in document_cache_dir.glob("*.json"):
        try:
            cache_file.unlink()
            deleted_count += 1
        except OSError:
            continue

    try:
        document_cache_dir.rmdir()
    except OSError:
        pass

    return deleted_count