import inspect
from datetime import datetime
from typing import Callable, Optional

from notion_client import Client

from src.config.settings import NOTION_API_KEY, NOTION_PARENT_PAGE_ID
from src.models.chapter_models import (
    ChapterFlashcardItem,
    ChapterLearningNote,
    ChapterQuizItem,
)
from src.services.chapter_cache_service import (
    is_valid_chapter_note,
    load_chapter_cache,
    mark_chapter_note_cache_invalid,
    save_chapter_note_cache,
    save_visual_context_cache,
)
from src.services.chapter_service import analyze_chapter
from src.services.export_state_service import (
    get_pending_chapters,
    is_chapter_completed,
    load_export_state,
    mark_chapter_completed,
    mark_chapter_failed,
    mark_export_finished,
    reset_export_state,
    set_parent_page,
)
from src.services.pdf_visual_service import analyze_chapter_visuals


MAX_RICH_TEXT_LENGTH = 1800
MAX_BLOCKS_PER_REQUEST = 80


def _get_function_parameter_names(function) -> list[str]:
    """取得函式參數名稱。"""

    try:
        return list(inspect.signature(function).parameters.keys())
    except Exception:
        return []


def _try_call(function, call_patterns: list[dict | tuple]):
    """
    依序嘗試不同呼叫方式。

    call_patterns 可以放：
    - dict：用 keyword arguments 呼叫
    - tuple：用 positional arguments 呼叫
    """

    last_error = None

    for pattern in call_patterns:
        try:
            if isinstance(pattern, dict):
                return function(**pattern)

            return function(*pattern)

        except TypeError as error:
            last_error = error
            continue

    if last_error:
        raise last_error

    raise TypeError(f"無法呼叫函式：{function.__name__}")


def _safe_load_export_state(
    document_name: str,
    chapter_count: int,
) -> dict:
    """相容不同版本的 load_export_state。"""

    return _try_call(
        load_export_state,
        [
            {
                "document_name": document_name,
                "chapter_count": chapter_count,
            },
            {
                "document_name": document_name,
            },
            (
                document_name,
                chapter_count,
            ),
            (
                document_name,
            ),
        ],
    )


def _safe_reset_export_state(
    document_name: str,
    chapter_count: int,
) -> dict | None:
    """相容不同版本的 reset_export_state。"""

    return _try_call(
        reset_export_state,
        [
            {
                "document_name": document_name,
                "chapter_count": chapter_count,
            },
            {
                "document_name": document_name,
            },
            (
                document_name,
                chapter_count,
            ),
            (
                document_name,
            ),
        ],
    )


def _safe_set_parent_page(
    document_name: str,
    state: dict,
    parent_page_id: str,
    parent_page_url: str | None,
) -> dict | None:
    """相容不同版本的 set_parent_page。"""

    return _try_call(
        set_parent_page,
        [
            {
                "document_name": document_name,
                "state": state,
                "parent_page_id": parent_page_id,
                "parent_page_url": parent_page_url,
            },
            {
                "state": state,
                "parent_page_id": parent_page_id,
                "parent_page_url": parent_page_url,
            },
            {
                "document_name": document_name,
                "parent_page_id": parent_page_id,
                "parent_page_url": parent_page_url,
            },
            (
                document_name,
                state,
                parent_page_id,
                parent_page_url,
            ),
            (
                state,
                parent_page_id,
                parent_page_url,
            ),
            (
                document_name,
                parent_page_id,
                parent_page_url,
            ),
        ],
    )


def _safe_get_pending_chapters(
    document_name: str,
    state: dict,
    chapters: list[dict],
) -> list[dict]:
    """相容不同版本的 get_pending_chapters。"""

    return _try_call(
        get_pending_chapters,
        [
            {
                "document_name": document_name,
                "state": state,
                "chapters": chapters,
            },
            {
                "document_name": document_name,
                "chapters": chapters,
            },
            {
                "state": state,
                "chapters": chapters,
            },
            {
                "export_state": state,
                "chapters": chapters,
            },
            (
                document_name,
                state,
                chapters,
            ),
            (
                state,
                chapters,
            ),
            (
                document_name,
                chapters,
            ),
            (
                chapters,
            ),
        ],
    )


def _safe_is_chapter_completed(
    document_name: str,
    state: dict,
    chapter_id: str,
) -> bool:
    """相容不同版本的 is_chapter_completed。"""

    return bool(
        _try_call(
            is_chapter_completed,
            [
                {
                    "document_name": document_name,
                    "state": state,
                    "chapter_id": chapter_id,
                },
                {
                    "document_name": document_name,
                    "chapter_id": chapter_id,
                },
                {
                    "state": state,
                    "chapter_id": chapter_id,
                },
                {
                    "export_state": state,
                    "chapter_id": chapter_id,
                },
                (
                    document_name,
                    state,
                    chapter_id,
                ),
                (
                    state,
                    chapter_id,
                ),
                (
                    document_name,
                    chapter_id,
                ),
                (
                    chapter_id,
                ),
            ],
        )
    )


def _safe_mark_chapter_completed(
    document_name: str,
    state: dict,
    chapter_id: str,
    chapter_title: str,
    notion_page_id: str,
    notion_page_url: str | None,
) -> dict | None:
    """相容不同版本的 mark_chapter_completed。"""

    return _try_call(
        mark_chapter_completed,
        [
            {
                "document_name": document_name,
                "state": state,
                "chapter_id": chapter_id,
                "chapter_title": chapter_title,
                "notion_page_id": notion_page_id,
                "notion_page_url": notion_page_url,
            },
            {
                "state": state,
                "chapter_id": chapter_id,
                "chapter_title": chapter_title,
                "notion_page_id": notion_page_id,
                "notion_page_url": notion_page_url,
            },
            {
                "document_name": document_name,
                "chapter_id": chapter_id,
                "chapter_title": chapter_title,
                "notion_page_id": notion_page_id,
                "notion_page_url": notion_page_url,
            },
            (
                document_name,
                state,
                chapter_id,
                chapter_title,
                notion_page_id,
                notion_page_url,
            ),
            (
                state,
                chapter_id,
                chapter_title,
                notion_page_id,
                notion_page_url,
            ),
            (
                document_name,
                chapter_id,
                chapter_title,
                notion_page_id,
                notion_page_url,
            ),
        ],
    )


def _safe_mark_chapter_failed(
    document_name: str,
    state: dict,
    chapter_id: str,
    chapter_title: str,
    error: str,
) -> dict | None:
    """相容不同版本的 mark_chapter_failed。"""

    return _try_call(
        mark_chapter_failed,
        [
            {
                "document_name": document_name,
                "state": state,
                "chapter_id": chapter_id,
                "chapter_title": chapter_title,
                "error": error,
            },
            {
                "state": state,
                "chapter_id": chapter_id,
                "chapter_title": chapter_title,
                "error": error,
            },
            {
                "document_name": document_name,
                "chapter_id": chapter_id,
                "chapter_title": chapter_title,
                "error": error,
            },
            (
                document_name,
                state,
                chapter_id,
                chapter_title,
                error,
            ),
            (
                state,
                chapter_id,
                chapter_title,
                error,
            ),
            (
                document_name,
                chapter_id,
                chapter_title,
                error,
            ),
        ],
    )


def _safe_mark_export_finished(
    document_name: str,
    state: dict,
) -> dict | None:
    """相容不同版本的 mark_export_finished。"""

    return _try_call(
        mark_export_finished,
        [
            {
                "document_name": document_name,
                "state": state,
            },
            {
                "state": state,
            },
            {
                "document_name": document_name,
            },
            (
                document_name,
                state,
            ),
            (
                state,
            ),
            (
                document_name,
            ),
        ],
    )


def _get_notion_client() -> Client:
    """建立 Notion Client。"""

    if not NOTION_API_KEY:
        raise ValueError("尚未設定 NOTION_API_KEY。")

    return Client(auth=NOTION_API_KEY)


def _chunk_text(
    text: str,
    max_length: int = MAX_RICH_TEXT_LENGTH,
) -> list[str]:
    """將過長文字切成 Notion rich_text 可接受的長度。"""

    if text is None:
        return []

    text = str(text).strip()

    if not text:
        return []

    chunks = []
    current = ""

    for line in text.splitlines():
        if len(current) + len(line) + 1 <= max_length:
            current = f"{current}\n{line}".strip()
        else:
            if current:
                chunks.append(current)

            if len(line) <= max_length:
                current = line
            else:
                for index in range(0, len(line), max_length):
                    chunks.append(line[index:index + max_length])

                current = ""

    if current:
        chunks.append(current)

    return chunks


def _rich_text(text: str) -> list[dict]:
    """建立 Notion rich_text。"""

    parts = _chunk_text(text)

    if not parts:
        return [
            {
                "type": "text",
                "text": {
                    "content": "",
                },
            }
        ]

    return [
        {
            "type": "text",
            "text": {
                "content": part,
            },
        }
        for part in parts
    ]


def _paragraph(text: str) -> list[dict]:
    """建立 paragraph blocks。"""

    blocks = []

    for part in _chunk_text(text):
        blocks.append(
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": _rich_text(part),
                },
            }
        )

    return blocks


def _heading_1(text: str) -> dict:
    """建立 heading 1 block。"""

    return {
        "object": "block",
        "type": "heading_1",
        "heading_1": {
            "rich_text": _rich_text(text),
        },
    }


def _heading_2(text: str) -> dict:
    """建立 heading 2 block。"""

    return {
        "object": "block",
        "type": "heading_2",
        "heading_2": {
            "rich_text": _rich_text(text),
        },
    }


def _heading_3(text: str) -> dict:
    """建立 heading 3 block。"""

    return {
        "object": "block",
        "type": "heading_3",
        "heading_3": {
            "rich_text": _rich_text(text),
        },
    }


def _bulleted_item(text: str) -> list[dict]:
    """建立 bulleted list item。"""

    blocks = []

    for part in _chunk_text(text):
        blocks.append(
            {
                "object": "block",
                "type": "bulleted_list_item",
                "bulleted_list_item": {
                    "rich_text": _rich_text(part),
                },
            }
        )

    return blocks


def _callout(text: str, icon: str = "💡") -> dict:
    """建立 callout block。"""

    return {
        "object": "block",
        "type": "callout",
        "callout": {
            "rich_text": _rich_text(text),
            "icon": {
                "type": "emoji",
                "emoji": icon,
            },
        },
    }


def _code_block(
    code: str,
    language: str = "plain text",
) -> dict:
    """建立 code block。"""

    if not code:
        code = ""

    safe_language = language or "plain text"

    return {
        "object": "block",
        "type": "code",
        "code": {
            "rich_text": _rich_text(code),
            "language": safe_language,
        },
    }


def _divider() -> dict:
    """建立 divider block。"""

    return {
        "object": "block",
        "type": "divider",
        "divider": {},
    }


def _table_block(
    headers: list[str],
    rows: list[list[str]],
) -> Optional[dict]:
    """建立 Notion table block。"""

    if not headers or not rows:
        return None

    table_rows = []

    header_cells = []

    for header in headers:
        header_cells.append(_rich_text(header))

    table_rows.append(
        {
            "object": "block",
            "type": "table_row",
            "table_row": {
                "cells": header_cells,
            },
        }
    )

    for row in rows:
        cells = []

        for index in range(len(headers)):
            cell_text = row[index] if index < len(row) else ""
            cells.append(_rich_text(cell_text))

        table_rows.append(
            {
                "object": "block",
                "type": "table_row",
                "table_row": {
                    "cells": cells,
                },
            }
        )

    return {
        "object": "block",
        "type": "table",
        "table": {
            "table_width": len(headers),
            "has_column_header": True,
            "has_row_header": False,
            "children": table_rows,
        },
    }


def _append_blocks(
    notion: Client,
    page_id: str,
    blocks: list[dict],
) -> None:
    """分批 append blocks，避免 Notion API block 數量限制。"""

    if not blocks:
        return

    for index in range(0, len(blocks), MAX_BLOCKS_PER_REQUEST):
        batch = blocks[index:index + MAX_BLOCKS_PER_REQUEST]

        notion.blocks.children.append(
            block_id=page_id,
            children=batch,
        )


def _create_page(
    notion: Client,
    title: str,
    parent_page_id: str,
) -> dict:
    """建立 Notion 子頁。"""

    return notion.pages.create(
        parent={
            "type": "page_id",
            "page_id": parent_page_id,
        },
        properties={
            "title": {
                "title": [
                    {
                        "type": "text",
                        "text": {
                            "content": title[:200],
                        },
                    }
                ]
            }
        },
    )


def _create_parent_page(
    notion: Client,
    document_name: str,
) -> dict:
    """建立整份文件的 Notion 父頁。"""

    if not NOTION_PARENT_PAGE_ID:
        raise ValueError("尚未設定 NOTION_PARENT_PAGE_ID。")

    title = f"📘 {document_name}｜AI 詳細學習筆記"

    return _create_page(
        notion=notion,
        title=title,
        parent_page_id=NOTION_PARENT_PAGE_ID,
    )


def _build_quiz_blocks(quiz_items: list[ChapterQuizItem]) -> list[dict]:
    """建立 Quiz blocks。"""

    blocks = []

    if not quiz_items:
        blocks.extend(_paragraph("本章未產生 Quiz。"))
        return blocks

    for index, item in enumerate(quiz_items, start=1):
        blocks.append(_heading_3(f"第 {index} 題"))
        blocks.extend(_paragraph(f"Q：{item.question}"))
        blocks.extend(_paragraph(f"A：{item.answer}"))

        if item.explanation:
            blocks.extend(_paragraph(f"解析：{item.explanation}"))

    return blocks


def _build_flashcard_blocks(
    flashcards: list[ChapterFlashcardItem],
) -> list[dict]:
    """建立 Flash Card blocks。"""

    blocks = []

    if not flashcards:
        blocks.extend(_paragraph("本章未產生 Flash Cards。"))
        return blocks

    for index, card in enumerate(flashcards, start=1):
        blocks.append(_heading_3(f"Flash Card {index}"))
        blocks.extend(_paragraph(f"正面：{card.front}"))
        blocks.extend(_paragraph(f"背面：{card.back}"))

    return blocks


def _build_chapter_note_blocks(
    chapter_note: ChapterLearningNote,
) -> list[dict]:
    """將 ChapterLearningNote 轉成 Notion blocks。"""

    is_valid, reason = is_valid_chapter_note(chapter_note)

    if not is_valid:
        raise ValueError(f"拒絕建立空白 Notion 子頁：{reason}")

    blocks = []

    blocks.append(_heading_1(f"📘 {chapter_note.chapter_title}"))

    blocks.append(
        _callout(
            "本頁由 AI Notion 自動筆記整理器產生，內容包含摘要、白話講解、重點、術語、練習題與複習素材。",
            icon="📝",
        )
    )

    blocks.append(_divider())

    blocks.append(_heading_2("🎯 學習目標"))

    if chapter_note.learning_objectives:
        for objective in chapter_note.learning_objectives:
            blocks.extend(_bulleted_item(objective))
    else:
        blocks.extend(_paragraph("本章未產生明確學習目標。"))

    blocks.append(_heading_2("📝 章節摘要"))
    blocks.extend(_paragraph(chapter_note.chapter_summary))

    blocks.append(_heading_2("🧠 白話講解"))
    blocks.extend(_paragraph(chapter_note.plain_explanation))

    blocks.append(_heading_2("⭐ 核心重點"))

    if chapter_note.key_points:
        for point in chapter_note.key_points:
            blocks.extend(_bulleted_item(point))
    else:
        blocks.extend(_paragraph("本章未產生核心重點。"))

    blocks.append(_heading_2("📚 重要術語"))

    if chapter_note.important_terms:
        for term in chapter_note.important_terms:
            blocks.extend(_bulleted_item(term))
    else:
        blocks.extend(_paragraph("本章未產生重要術語。"))

    blocks.append(_heading_2("📌 語法規則與注意事項"))

    if chapter_note.syntax_rules:
        for rule in chapter_note.syntax_rules:
            blocks.extend(_bulleted_item(rule))
    else:
        blocks.extend(_paragraph("本章未產生語法規則。"))

    if chapter_note.callout_notes:
        blocks.append(_heading_2("✨ 重點標註"))

        for callout_note in chapter_note.callout_notes:
            title = callout_note.title or "補充提醒"
            content = callout_note.content or ""
            icon = callout_note.icon or "💡"

            blocks.append(
                _callout(
                    f"{title}\n\n{content}",
                    icon=icon,
                )
            )

    if chapter_note.comparison_tables:
        blocks.append(_heading_2("📊 重點比較表"))

        for table in chapter_note.comparison_tables:
            blocks.append(_heading_3(table.title))

            table_block = _table_block(
                headers=table.headers,
                rows=table.rows,
            )

            if table_block:
                blocks.append(table_block)

            if table.note:
                blocks.extend(_paragraph(f"補充：{table.note}"))

    blocks.append(_heading_2("💻 程式碼範例"))

    if chapter_note.code_examples:
        for index, example in enumerate(
            chapter_note.code_examples,
            start=1,
        ):
            blocks.append(_heading_3(f"範例 {index}｜{example.title}"))
            blocks.append(
                _code_block(
                    code=example.code,
                    language=example.language or "plain text",
                )
            )
            blocks.extend(_paragraph(example.explanation))
    else:
        blocks.extend(_paragraph("本章未產生程式碼範例。"))

    blocks.append(_heading_2("⚠️ 常見錯誤與混淆"))

    if chapter_note.common_mistakes:
        for index, mistake in enumerate(
            chapter_note.common_mistakes,
            start=1,
        ):
            blocks.append(_heading_3(f"常見錯誤 {index}"))
            blocks.extend(_paragraph(f"容易出錯：{mistake.mistake}"))
            blocks.extend(_paragraph(f"正確觀念：{mistake.correction}"))
    else:
        blocks.extend(_paragraph("本章未產生常見錯誤提醒。"))

    blocks.append(_heading_2("🧩 子章節整理"))

    if chapter_note.subsections:
        for subsection in chapter_note.subsections:
            blocks.append(_heading_3(subsection.title))
            blocks.extend(_paragraph(subsection.summary))

            if subsection.key_points:
                blocks.extend(_paragraph("重點："))

                for point in subsection.key_points:
                    blocks.extend(_bulleted_item(point))

            if subsection.important_terms:
                blocks.extend(_paragraph("術語："))

                for term in subsection.important_terms:
                    blocks.extend(_bulleted_item(term))
    else:
        blocks.extend(_paragraph("本章未產生子章節整理。"))

    blocks.append(_heading_2("🖼️ PDF 圖片與畫面解讀"))

    if chapter_note.image_insights:
        for image in chapter_note.image_insights:
            blocks.append(
                _heading_3(
                    f"第 {image.page_number} 頁｜{image.title}"
                )
            )
            blocks.extend(_paragraph(f"圖片類型：{image.image_type}"))
            blocks.extend(_paragraph(image.description))

            if image.related_subsection:
                blocks.extend(
                    _paragraph(
                        f"對應子章節：{image.related_subsection}"
                    )
                )

            if image.learning_points:
                blocks.extend(_paragraph("從圖片可學到："))

                for point in image.learning_points:
                    blocks.extend(_bulleted_item(point))
    else:
        blocks.extend(_paragraph("本章未產生 PDF 視覺補充。"))

    blocks.append(_heading_2("🧪 練習建議"))

    if chapter_note.practice_tips:
        for index, tip in enumerate(
            chapter_note.practice_tips,
            start=1,
        ):
            blocks.append(_heading_3(f"練習 {index}｜{tip.title}"))
            blocks.extend(_paragraph(f"操作：{tip.instruction}"))

            if tip.expected_result:
                blocks.extend(
                    _paragraph(f"預期成果：{tip.expected_result}")
                )
    else:
        blocks.extend(_paragraph("本章未產生練習建議。"))

    blocks.append(_heading_2("🗺️ 章節學習地圖"))

    if chapter_note.mermaid:
        blocks.append(
            _code_block(
                code=chapter_note.mermaid,
                language="plain text",
            )
        )
    else:
        blocks.extend(_paragraph("本章未產生 Mermaid 學習地圖。"))

    blocks.append(_heading_2("❓ 章節 Quiz"))
    blocks.extend(_build_quiz_blocks(chapter_note.quiz))

    blocks.append(_heading_2("🗂️ 章節 Flash Cards"))
    blocks.extend(_build_flashcard_blocks(chapter_note.flashcards))

    return blocks


def _get_visual_context(
    document_name: str,
    chapter: dict,
    parsed_document: dict,
    cached_data: dict,
) -> tuple[list[dict], bool]:
    """
    取得 PDF 視覺分析內容。

    回傳：
    - visual_context
    - used_cache
    """

    is_pdf = parsed_document.get("metadata", {}).get(
        "file_extension"
    ) == ".pdf"

    has_pdf_data = (
        parsed_document.get("pdf_bytes")
        and parsed_document.get("page_texts")
    )

    if cached_data.get("visual_cached"):
        return cached_data.get("visual_context", []), True

    if not is_pdf or not has_pdf_data:
        save_visual_context_cache(
            document_name=document_name,
            chapter=chapter,
            visual_context=[],
        )

        return [], False

    visual_context = analyze_chapter_visuals(
        chapter=chapter,
        pdf_bytes=parsed_document["pdf_bytes"],
        page_texts=parsed_document["page_texts"],
        max_pages=3,
    )

    save_visual_context_cache(
        document_name=document_name,
        chapter=chapter,
        visual_context=visual_context,
    )

    return visual_context, False


def _get_chapter_note(
    document_name: str,
    chapter: dict,
    visual_context: list[dict],
    cached_data: dict,
    force_regenerate_note: bool,
) -> tuple[ChapterLearningNote, bool]:
    """
    取得章節詳細筆記。

    回傳：
    - chapter_note
    - used_cache
    """

    cached_note = cached_data.get("chapter_note")
    note_cached = cached_data.get("note_cached", False)
    note_cache_valid = cached_data.get("note_cache_valid", False)

    if (
        not force_regenerate_note
        and note_cached
        and note_cache_valid
        and cached_note is not None
    ):
        return cached_note, True

    if note_cached and not note_cache_valid:
        mark_chapter_note_cache_invalid(
            document_name=document_name,
            chapter=chapter,
            reason=cached_data.get(
                "note_cache_invalid_reason",
                "詳細筆記快取無效",
            ),
        )

    chapter_note = analyze_chapter(
        chapter=chapter,
        visual_context=visual_context,
    )

    is_valid, reason = is_valid_chapter_note(chapter_note)

    if not is_valid:
        mark_chapter_note_cache_invalid(
            document_name=document_name,
            chapter=chapter,
            reason=reason,
        )

        raise ValueError(f"AI 產生的詳細筆記無效：{reason}")

    save_chapter_note_cache(
        document_name=document_name,
        chapter=chapter,
        chapter_note=chapter_note,
    )

    return chapter_note, False


def create_document_learning_notebook(
    document_name: str,
    chapters: list[dict],
    parsed_document: dict,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
    max_visual_pages: int = 3,
    resume: bool = True,
) -> dict:
    """
    建立整份文件的 Notion 詳細學習筆記。

    resume=True：
    - 跳過已完成章節
    - pending / failed 章節會重新處理
    - failed 章節會強制重新生成詳細筆記，避免壞快取一直建立空頁

    resume=False：
    - 重置匯出狀態
    - 從頭建立新的 Notion 父頁與章節子頁
    - 仍會使用有效 AI 快取
    """

    notion = _get_notion_client()
    chapter_count = len(chapters)

    if not resume:
        _safe_reset_export_state(
            document_name=document_name,
            chapter_count=chapter_count,
        )

    export_state = _safe_load_export_state(
        document_name=document_name,
        chapter_count=chapter_count,
    )

    parent_page_id = export_state.get("parent_page_id")
    parent_page_url = export_state.get("parent_page_url")

    if not parent_page_id:
        parent_page = _create_parent_page(
            notion=notion,
            document_name=document_name,
        )

        parent_page_id = parent_page["id"]
        parent_page_url = parent_page.get("url")

        _safe_set_parent_page(
            document_name=document_name,
            state=export_state,
            parent_page_id=parent_page_id,
            parent_page_url=parent_page_url,
        )

        export_state = _safe_load_export_state(
            document_name=document_name,
            chapter_count=chapter_count,
        )

    pending_chapters = _safe_get_pending_chapters(
        document_name=document_name,
        state=export_state,
        chapters=chapters,
    )

    total_count = len(pending_chapters)

    completed_this_run = []
    failed_this_run = []
    cached_visual_count = 0
    cached_note_count = 0
    regenerated_note_count = 0
    processed_chapter_count = 0

    if total_count == 0:
        _safe_mark_export_finished(
            document_name=document_name,
            state=export_state,
        )

        final_state = _safe_load_export_state(
            document_name=document_name,
            chapter_count=chapter_count,
        )

        return {
            "document_name": document_name,
            "parent_page_id": parent_page_id,
            "parent_page_url": parent_page_url,
            "completed_chapters": final_state.get(
                "completed_chapters",
                [],
            ),
            "failed_chapters": final_state.get(
                "failed_chapters",
                [],
            ),
            "processed_chapter_count": 0,
            "cached_visual_count": 0,
            "cached_note_count": 0,
            "regenerated_note_count": 0,
            "is_finished": True,
        }

    for index, chapter in enumerate(pending_chapters, start=1):
        chapter_id = str(chapter.get("chapter_id"))
        chapter_title = chapter.get("title", f"Module {chapter_id}")

        export_state = _safe_load_export_state(
            document_name=document_name,
            chapter_count=chapter_count,
        )

        if _safe_is_chapter_completed(
            document_name=document_name,
            state=export_state,
            chapter_id=chapter_id,
        ):
            continue

        if progress_callback:
            progress_callback(
                index,
                total_count,
                f"正在處理 {chapter_title}...",
            )

        try:
            cached_data = load_chapter_cache(
                document_name=document_name,
                chapter=chapter,
            )

            visual_context, visual_used_cache = _get_visual_context(
                document_name=document_name,
                chapter=chapter,
                parsed_document=parsed_document,
                cached_data=cached_data,
            )

            if visual_used_cache:
                cached_visual_count += 1

            force_regenerate_note = bool(
                cached_data.get("note_cached")
                and not cached_data.get("note_cache_valid")
            )

            chapter_note, note_used_cache = _get_chapter_note(
                document_name=document_name,
                chapter=chapter,
                visual_context=visual_context,
                cached_data=cached_data,
                force_regenerate_note=force_regenerate_note,
            )

            if note_used_cache:
                cached_note_count += 1
            else:
                regenerated_note_count += 1

            is_valid, reason = is_valid_chapter_note(chapter_note)

            if not is_valid:
                raise ValueError(
                    f"拒絕建立 Notion 子頁，詳細筆記無效：{reason}"
                )

            child_page_title = f"Module {chapter_id}｜{chapter_title}"

            child_page = _create_page(
                notion=notion,
                title=child_page_title,
                parent_page_id=parent_page_id,
            )

            child_page_id = child_page["id"]
            child_page_url = child_page.get("url")

            blocks = _build_chapter_note_blocks(chapter_note)

            if not blocks:
                raise ValueError("章節 blocks 為空，拒絕建立空白 Notion 子頁。")

            _append_blocks(
                notion=notion,
                page_id=child_page_id,
                blocks=blocks,
            )

            export_state = _safe_load_export_state(
                document_name=document_name,
                chapter_count=chapter_count,
            )

            _safe_mark_chapter_completed(
                document_name=document_name,
                state=export_state,
                chapter_id=chapter_id,
                chapter_title=chapter_title,
                notion_page_id=child_page_id,
                notion_page_url=child_page_url,
            )

            completed_this_run.append(
                {
                    "chapter_id": chapter_id,
                    "chapter_title": chapter_title,
                    "notion_page_id": child_page_id,
                    "notion_page_url": child_page_url,
                }
            )

            processed_chapter_count += 1

        except Exception as error:
            error_message = str(error)

            export_state = _safe_load_export_state(
                document_name=document_name,
                chapter_count=chapter_count,
            )

            _safe_mark_chapter_failed(
                document_name=document_name,
                state=export_state,
                chapter_id=chapter_id,
                chapter_title=chapter_title,
                error=error_message,
            )

            failed_this_run.append(
                {
                    "chapter_id": chapter_id,
                    "chapter_title": chapter_title,
                    "error": error_message,
                }
            )

    final_state = _safe_load_export_state(
        document_name=document_name,
        chapter_count=chapter_count,
    )

    remaining_pending = _safe_get_pending_chapters(
        document_name=document_name,
        state=final_state,
        chapters=chapters,
    )

    is_finished = len(remaining_pending) == 0

    if is_finished:
        _safe_mark_export_finished(
            document_name=document_name,
            state=final_state,
        )

        final_state = _safe_load_export_state(
            document_name=document_name,
            chapter_count=chapter_count,
        )

    return {
        "document_name": document_name,
        "parent_page_id": parent_page_id,
        "parent_page_url": parent_page_url,
        "completed_chapters": final_state.get(
            "completed_chapters",
            [],
        ),
        "failed_chapters": final_state.get(
            "failed_chapters",
            [],
        ),
        "completed_this_run": completed_this_run,
        "failed_this_run": failed_this_run,
        "processed_chapter_count": processed_chapter_count,
        "cached_visual_count": cached_visual_count,
        "cached_note_count": cached_note_count,
        "regenerated_note_count": regenerated_note_count,
        "is_finished": is_finished,
        "updated_at": datetime.utcnow().isoformat(),
    }