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
    """將文件名稱轉成可用於資料夾 / 檔名的安全名稱。"""

    safe_name = Path(file_name).stem
    safe_name = re.sub(r'[\\/:*?"<>|]+', "_", safe_name)
    safe_name = safe_name.strip()

    if not safe_name:
        safe_name = "untitled_document"

    return safe_name


def _chapter_content_hash(chapter: dict) -> str:
    """依照章節標題與內容產生穩定 hash。"""

    chapter_id = str(chapter.get("chapter_id", ""))
    title = str(chapter.get("title", ""))
    content = str(chapter.get("content", ""))

    raw = f"{chapter_id}|{title}|{content}"

    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]


def _get_document_cache_dir(document_name: str) -> Path:
    """取得某份文件的章節快取資料夾。"""

    document_dir = CHAPTER_CACHE_DIR / _safe_file_name(document_name)
    document_dir.mkdir(parents=True, exist_ok=True)

    return document_dir


def _get_chapter_cache_path(
    document_name: str,
    chapter: dict,
) -> Path:
    """取得單一章節快取檔案路徑。"""

    document_dir = _get_document_cache_dir(document_name)
    chapter_id = str(chapter.get("chapter_id", "unknown"))
    chapter_hash = _chapter_content_hash(chapter)

    return document_dir / f"chapter_{chapter_id}_{chapter_hash}.json"


def _empty_cache_state() -> dict:
    """建立空的快取狀態。"""

    return {
        "cache_version": CACHE_VERSION,
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
        "visual_analysis_completed": False,
        "visual_context": [],
        "chapter_note_completed": False,
        "chapter_note": None,
    }


def _read_cache_file(cache_path: Path) -> dict:
    """讀取快取檔案，失敗時回傳空快取。"""

    if not cache_path.exists():
        return _empty_cache_state()

    try:
        with cache_path.open("r", encoding="utf-8") as file:
            cache_data = json.load(file)

        if not isinstance(cache_data, dict):
            return _empty_cache_state()

        if cache_data.get("cache_version") != CACHE_VERSION:
            return _empty_cache_state()

        return cache_data

    except Exception:
        return _empty_cache_state()


def _write_cache_file(
    cache_path: Path,
    cache_data: dict,
) -> None:
    """寫入快取檔案。"""

    cache_data["cache_version"] = CACHE_VERSION
    cache_data["updated_at"] = datetime.utcnow().isoformat()

    cache_path.parent.mkdir(parents=True, exist_ok=True)

    with cache_path.open("w", encoding="utf-8") as file:
        json.dump(
            cache_data,
            file,
            ensure_ascii=False,
            indent=2,
        )


def _remove_image_data_url(visual_context: list[dict]) -> list[dict]:
    """移除 Base64 圖片資料，避免快取檔案過大。"""

    cleaned_items = []

    for item in visual_context:
        if not isinstance(item, dict):
            continue

        cleaned_item = dict(item)
        cleaned_item.pop("image_data_url", None)
        cleaned_items.append(cleaned_item)

    return cleaned_items


def _text_is_meaningful(value: Any) -> bool:
    """判斷文字欄位是否有有效內容。"""

    if not isinstance(value, str):
        return False

    cleaned = value.strip()

    if not cleaned:
        return False

    empty_values = {
        "無",
        "沒有",
        "none",
        "null",
        "n/a",
        "N/A",
        "未提供",
        "無資料",
    }

    return cleaned not in empty_values


def is_valid_chapter_note(chapter_note: Any) -> tuple[bool, str]:
    """
    檢查 ChapterLearningNote 是否有效。

    這個函式用來避免續跑時讀到壞快取，然後一直建立空的 Notion 子頁。
    """

    if chapter_note is None:
        return False, "chapter_note 是 None"

    if not isinstance(chapter_note, ChapterLearningNote):
        return False, "chapter_note 不是 ChapterLearningNote 物件"

    if not _text_is_meaningful(chapter_note.chapter_title):
        return False, "章節標題是空的"

    meaningful_text_fields = [
        chapter_note.chapter_summary,
        chapter_note.plain_explanation,
    ]

    meaningful_text_count = sum(
        1 for value in meaningful_text_fields if _text_is_meaningful(value)
    )

    list_field_count = 0

    list_fields = [
        chapter_note.learning_objectives,
        chapter_note.key_points,
        chapter_note.important_terms,
        chapter_note.syntax_rules,
        chapter_note.code_examples,
        chapter_note.common_mistakes,
        chapter_note.subsections,
        chapter_note.callout_notes,
        chapter_note.comparison_tables,
        chapter_note.image_insights,
        chapter_note.practice_tips,
        chapter_note.quiz,
        chapter_note.flashcards,
    ]

    for field in list_fields:
        if field:
            list_field_count += 1

    has_mermaid = _text_is_meaningful(chapter_note.mermaid)

    quality_score = meaningful_text_count + list_field_count

    if has_mermaid:
        quality_score += 1

    if quality_score < 3:
        return (
            False,
            "詳細筆記內容過少，可能是壞快取或 AI 回傳空內容",
        )

    if (
        not chapter_note.key_points
        and not chapter_note.important_terms
        and not chapter_note.subsections
        and not chapter_note.quiz
        and not chapter_note.flashcards
    ):
        return (
            False,
            "缺少重點、術語、子章節、Quiz、Flash Cards 等主要內容",
        )

    return True, "有效詳細筆記"


def load_chapter_cache(
    document_name: str,
    chapter: dict,
) -> dict:
    """
    讀取單一章節快取。

    回傳：
    - visual_context
    - visual_cached
    - chapter_note
    - note_cached
    - note_cache_valid
    - note_cache_invalid_reason
    - cache_path
    """

    cache_path = _get_chapter_cache_path(
        document_name=document_name,
        chapter=chapter,
    )

    cache_data = _read_cache_file(cache_path)

    visual_context = cache_data.get("visual_context", [])
    visual_cached = bool(
        cache_data.get("visual_analysis_completed", False)
    )

    chapter_note = None
    note_cached = False
    note_cache_valid = False
    note_cache_invalid_reason = "沒有詳細筆記快取"

    if cache_data.get("chapter_note_completed"):
        raw_note = cache_data.get("chapter_note")

        if raw_note:
            try:
                chapter_note = ChapterLearningNote.model_validate(raw_note)
                note_cached = True

                note_cache_valid, note_cache_invalid_reason = (
                    is_valid_chapter_note(chapter_note)
                )

            except Exception as error:
                chapter_note = None
                note_cached = True
                note_cache_valid = False
                note_cache_invalid_reason = (
                    f"詳細筆記快取格式錯誤：{error}"
                )

    return {
        "visual_context": visual_context
        if isinstance(visual_context, list)
        else [],
        "visual_cached": visual_cached,
        "chapter_note": chapter_note,
        "note_cached": note_cached,
        "note_cache_valid": note_cache_valid,
        "note_cache_invalid_reason": note_cache_invalid_reason,
        "cache_path": cache_path,
    }


def save_visual_context_cache(
    document_name: str,
    chapter: dict,
    visual_context: list[dict],
) -> Path:
    """儲存 PDF 視覺分析快取。"""

    cache_path = _get_chapter_cache_path(
        document_name=document_name,
        chapter=chapter,
    )

    cache_data = _read_cache_file(cache_path)

    cache_data["visual_analysis_completed"] = True
    cache_data["visual_context"] = _remove_image_data_url(visual_context)
    cache_data["updated_at"] = datetime.utcnow().isoformat()

    _write_cache_file(cache_path, cache_data)

    return cache_path


def save_chapter_note_cache(
    document_name: str,
    chapter: dict,
    chapter_note: ChapterLearningNote,
) -> Path:
    """儲存章節詳細筆記快取。"""

    is_valid, reason = is_valid_chapter_note(chapter_note)

    if not is_valid:
        raise ValueError(
            f"拒絕儲存無效的章節詳細筆記快取：{reason}"
        )

    cache_path = _get_chapter_cache_path(
        document_name=document_name,
        chapter=chapter,
    )

    cache_data = _read_cache_file(cache_path)

    cache_data["chapter_note_completed"] = True
    cache_data["chapter_note"] = chapter_note.model_dump()
    cache_data["chapter_note_cache_validated_at"] = (
        datetime.utcnow().isoformat()
    )
    cache_data["updated_at"] = datetime.utcnow().isoformat()

    _write_cache_file(cache_path, cache_data)

    return cache_path


def mark_chapter_note_cache_invalid(
    document_name: str,
    chapter: dict,
    reason: str,
) -> Path:
    """將章節詳細筆記快取標記為無效，避免下次續跑繼續讀取壞快取。"""

    cache_path = _get_chapter_cache_path(
        document_name=document_name,
        chapter=chapter,
    )

    cache_data = _read_cache_file(cache_path)

    cache_data["chapter_note_completed"] = False
    cache_data["chapter_note_invalid"] = True
    cache_data["chapter_note_invalid_reason"] = reason
    cache_data["chapter_note_invalid_at"] = datetime.utcnow().isoformat()
    cache_data["updated_at"] = datetime.utcnow().isoformat()

    _write_cache_file(cache_path, cache_data)

    return cache_path


def clear_document_cache(document_name: str) -> None:
    """清除某份文件的所有章節快取。"""

    document_dir = CHAPTER_CACHE_DIR / _safe_file_name(document_name)

    if not document_dir.exists():
        return

    for cache_file in document_dir.glob("*.json"):
        cache_file.unlink()