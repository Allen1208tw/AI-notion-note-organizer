from __future__ import annotations

import math
from typing import Any

from src.services.chapter_cache_service import load_chapter_cache
from src.services.export_state_service import (
    get_pending_chapters,
    load_export_state,
)


# ============================================================
# 時間估算設定
# ============================================================

ESTIMATED_VISUAL_ANALYSIS_SECONDS = 65
ESTIMATED_CHAPTER_NOTE_SECONDS = 115
ESTIMATED_NOTION_EXPORT_SECONDS = 30


# ============================================================
# Token 估算設定
# ============================================================

CHARACTERS_PER_TEXT_TOKEN = 1.7

CHAPTER_NOTE_FIXED_INPUT_TOKENS = 2600
VISUAL_ANALYSIS_FIXED_INPUT_TOKENS = 900

ESTIMATED_IMAGE_INPUT_TOKENS_PER_PAGE = 1200
ESTIMATED_VISUAL_CONTEXT_TOKENS_PER_PAGE = 280
ESTIMATED_VISUAL_OUTPUT_TOKENS_PER_PAGE = 280

MIN_CHAPTER_NOTE_OUTPUT_TOKENS = 1500
MAX_CHAPTER_NOTE_OUTPUT_TOKENS = 6500

MAX_VISUAL_PAGES_PER_CHAPTER = 3


def _is_pdf_document(parsed_document: dict) -> bool:
    """判斷目前文件是否為 PDF。"""

    metadata = parsed_document.get("metadata", {})

    return metadata.get("file_extension") == ".pdf"


def _estimate_text_tokens(text: str) -> int:
    """估算一般文字輸入 Token。"""

    cleaned_text = str(text or "").strip()

    if not cleaned_text:
        return 0

    return math.ceil(
        len(cleaned_text) / CHARACTERS_PER_TEXT_TOKEN
    )


def _estimate_visual_page_count(chapter: dict) -> int:
    """
    預估該 Module 會用多少 PDF 代表頁進行圖片分析。

    與目前流程對應：
    - 短 Module：1 張
    - 中 Module：2 張
    - 長 Module：3 張
    """

    content = str(chapter.get("content", ""))
    character_count = len(content)

    if character_count <= 3500:
        return 1

    if character_count <= 9000:
        return 2

    return MAX_VISUAL_PAGES_PER_CHAPTER


def _estimate_chapter_note_output_tokens(
    chapter: dict,
) -> int:
    """預估單一 Module 詳細筆記的輸出 Token。"""

    content = str(chapter.get("content", ""))
    source_tokens = _estimate_text_tokens(content)

    estimated_output = int(source_tokens * 0.65)

    return max(
        MIN_CHAPTER_NOTE_OUTPUT_TOKENS,
        min(
            estimated_output,
            MAX_CHAPTER_NOTE_OUTPUT_TOKENS,
        ),
    )


def _format_token_count(token_count: int) -> str:
    """將 Token 數量轉成易讀格式。"""

    if token_count < 1000:
        return f"{token_count:,}"

    return f"{token_count / 1000:.1f}K"


def _format_duration(seconds: int) -> str:
    """將秒數轉成容易閱讀的預估時間。"""

    if seconds <= 0:
        return "不需要執行"

    minutes = seconds / 60

    if minutes < 1:
        return "約 1 分鐘內"

    if minutes < 60:
        lower_minutes = max(1, round(minutes * 0.8))
        upper_minutes = max(lower_minutes + 1, round(minutes * 1.25))

        return f"約 {lower_minutes}～{upper_minutes} 分鐘"

    lower_hours = minutes * 0.8 / 60
    upper_hours = minutes * 1.25 / 60

    return f"約 {lower_hours:.1f}～{upper_hours:.1f} 小時"


def estimate_document_export(
    document_name: str,
    chapters: list[dict],
    parsed_document: dict,
    resume: bool = True,
) -> dict[str, Any]:
    """
    預估 Notion 詳細學習筆記匯出。

    包含：
    - 已有快取數量
    - 本次將新增的圖片分析快取頁數
    - 本次將新增的詳細筆記快取數
    - API input / output / total Token
    - 時間與 API 呼叫次數
    """

    chapter_count = len(chapters)

    empty_result = {
        "chapter_count": 0,
        "completed_count": 0,
        "pending_count": 0,
        "visual_cache_count": 0,
        "note_cache_count": 0,
        "need_visual_analysis_count": 0,
        "need_visual_analysis_page_count": 0,
        "need_note_generation_count": 0,
        "new_visual_cache_page_count": 0,
        "new_note_cache_count": 0,
        "need_notion_export_count": 0,
        "estimated_api_calls": 0,
        "estimated_input_tokens": 0,
        "estimated_output_tokens": 0,
        "estimated_total_tokens": 0,
        "estimated_input_tokens_text": "0",
        "estimated_output_tokens_text": "0",
        "estimated_total_tokens_text": "0",
        "estimated_seconds": 0,
        "estimated_time_text": "沒有可匯出的章節",
        "is_pdf": False,
        "resume": resume,
    }

    if chapter_count == 0:
        return empty_result

    state = load_export_state(
        document_name=document_name,
        chapter_count=chapter_count,
    )

    if resume:
        target_chapters = get_pending_chapters(
            chapters=chapters,
            state=state,
        )
        completed_count = len(
            state.get("completed_chapters", {})
        )
    else:
        target_chapters = chapters
        completed_count = 0

    is_pdf = _is_pdf_document(parsed_document)

    visual_cache_count = 0
    note_cache_count = 0

    need_visual_analysis_count = 0
    need_visual_analysis_page_count = 0
    need_note_generation_count = 0

    estimated_input_tokens = 0
    estimated_output_tokens = 0
    estimated_seconds = 0
    estimated_api_calls = 0

    for chapter in target_chapters:
        chapter_cache = load_chapter_cache(
            document_name=document_name,
            chapter=chapter,
        )

        chapter_content = str(chapter.get("content", ""))
        chapter_text_tokens = _estimate_text_tokens(
            chapter_content
        )

        visual_page_count = _estimate_visual_page_count(
            chapter
        )

        visual_cached = chapter_cache.get(
            "visual_cached",
            False,
        )

        note_cached = chapter_cache.get(
            "note_cached",
            False,
        )

        if is_pdf:
            if visual_cached:
                visual_cache_count += 1
            else:
                need_visual_analysis_count += 1
                need_visual_analysis_page_count += visual_page_count

                estimated_api_calls += 1
                estimated_seconds += (
                    ESTIMATED_VISUAL_ANALYSIS_SECONDS
                )

                estimated_input_tokens += (
                    VISUAL_ANALYSIS_FIXED_INPUT_TOKENS
                    + (
                        visual_page_count
                        * ESTIMATED_IMAGE_INPUT_TOKENS_PER_PAGE
                    )
                )

                estimated_output_tokens += (
                    visual_page_count
                    * ESTIMATED_VISUAL_OUTPUT_TOKENS_PER_PAGE
                )

        if note_cached:
            note_cache_count += 1
        else:
            need_note_generation_count += 1

            estimated_api_calls += 1
            estimated_seconds += (
                ESTIMATED_CHAPTER_NOTE_SECONDS
            )

            visual_context_tokens = 0

            if is_pdf:
                visual_context_tokens = (
                    visual_page_count
                    * ESTIMATED_VISUAL_CONTEXT_TOKENS_PER_PAGE
                )

            estimated_input_tokens += (
                CHAPTER_NOTE_FIXED_INPUT_TOKENS
                + chapter_text_tokens
                + visual_context_tokens
            )

            estimated_output_tokens += (
                _estimate_chapter_note_output_tokens(chapter)
            )

    pending_count = len(target_chapters)
    need_notion_export_count = pending_count

    estimated_seconds += (
        need_notion_export_count
        * ESTIMATED_NOTION_EXPORT_SECONDS
    )

    estimated_total_tokens = (
        estimated_input_tokens
        + estimated_output_tokens
    )

    return {
        "chapter_count": chapter_count,
        "completed_count": completed_count,
        "pending_count": pending_count,
        "visual_cache_count": visual_cache_count,
        "note_cache_count": note_cache_count,
        "need_visual_analysis_count": need_visual_analysis_count,
        "need_visual_analysis_page_count": (
            need_visual_analysis_page_count
        ),
        "need_note_generation_count": need_note_generation_count,
        "new_visual_cache_page_count": (
            need_visual_analysis_page_count
        ),
        "new_note_cache_count": need_note_generation_count,
        "need_notion_export_count": need_notion_export_count,
        "estimated_api_calls": estimated_api_calls,
        "estimated_input_tokens": estimated_input_tokens,
        "estimated_output_tokens": estimated_output_tokens,
        "estimated_total_tokens": estimated_total_tokens,
        "estimated_input_tokens_text": _format_token_count(
            estimated_input_tokens
        ),
        "estimated_output_tokens_text": _format_token_count(
            estimated_output_tokens
        ),
        "estimated_total_tokens_text": _format_token_count(
            estimated_total_tokens
        ),
        "estimated_seconds": estimated_seconds,
        "estimated_time_text": _format_duration(
            estimated_seconds
        ),
        "is_pdf": is_pdf,
        "resume": resume,
    }