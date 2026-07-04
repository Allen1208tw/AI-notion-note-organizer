from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from notion_client import Client

from src.config.settings import NOTION_API_KEY, NOTION_PARENT_PAGE_ID
from src.models.chapter_models import ChapterLearningNote
from src.services.chapter_cache_service import (
    load_chapter_cache,
    save_chapter_note_cache,
    save_visual_context_cache,
)
from src.services.chapter_service import analyze_chapter
from src.services.export_state_service import (
    get_pending_chapters,
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


def get_notion_client() -> Client:
    """建立 Notion API Client。"""

    if not NOTION_API_KEY:
        raise ValueError("找不到 NOTION_API_KEY，請確認 .env 設定。")

    return Client(auth=NOTION_API_KEY)


def _split_text(
    text: str,
    max_length: int = MAX_RICH_TEXT_LENGTH,
) -> list[str]:
    """
    將長文字切成安全片段。

    Notion 單一 text.content 上限為 2000 字元，
    此處保守使用 1800 字元。
    """

    cleaned_text = str(text or "").strip()

    if not cleaned_text:
        return []

    if len(cleaned_text) <= max_length:
        return [cleaned_text]

    parts = []
    remaining_text = cleaned_text

    while remaining_text:
        if len(remaining_text) <= max_length:
            parts.append(remaining_text)
            break

        split_index = remaining_text.rfind("\n", 0, max_length)

        if split_index < max_length * 0.5:
            split_index = remaining_text.rfind("。", 0, max_length)

        if split_index < max_length * 0.5:
            split_index = remaining_text.rfind("！", 0, max_length)

        if split_index < max_length * 0.5:
            split_index = remaining_text.rfind("？", 0, max_length)

        if split_index < max_length * 0.5:
            split_index = remaining_text.rfind("，", 0, max_length)

        if split_index < max_length * 0.5:
            split_index = remaining_text.rfind(" ", 0, max_length)

        if split_index < max_length * 0.5:
            split_index = max_length

        current_part = remaining_text[:split_index].strip()

        if current_part:
            parts.append(current_part)

        remaining_text = remaining_text[split_index:].strip()

    return parts


def text_content(text: str) -> list[dict]:
    """轉成 Notion rich_text 格式。"""

    return [
        {
            "type": "text",
            "text": {
                "content": part,
            },
        }
        for part in _split_text(text)
    ]


def _single_text_content(text: str) -> list[dict]:
    """建立單一安全 rich_text 內容。"""

    safe_text = str(text or "")[:MAX_RICH_TEXT_LENGTH]

    return [
        {
            "type": "text",
            "text": {
                "content": safe_text,
            },
        }
    ]


def heading_block(text: str, level: int = 2) -> dict:
    """建立 Heading Block。"""

    block_type = f"heading_{level}"

    return {
        "object": "block",
        "type": block_type,
        block_type: {
            "rich_text": text_content(text),
        },
    }


def paragraph_block(text: str) -> dict:
    """建立單一 Paragraph Block。"""

    return {
        "object": "block",
        "type": "paragraph",
        "paragraph": {
            "rich_text": text_content(text),
        },
    }


def paragraph_blocks(text: str) -> list[dict]:
    """將長文字拆成多個 Paragraph Block。"""

    return [
        {
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": _single_text_content(part),
            },
        }
        for part in _split_text(text)
    ]


def bullet_blocks(text: str) -> list[dict]:
    """將長文字拆成多個 Bullet Block。"""

    parts = _split_text(text)

    if not parts:
        return []

    blocks = []

    for index, part in enumerate(parts):
        prefix = "（續）" if index > 0 else ""

        blocks.append(
            {
                "object": "block",
                "type": "bulleted_list_item",
                "bulleted_list_item": {
                    "rich_text": _single_text_content(
                        f"{prefix}{part}"
                    ),
                },
            }
        )

    return blocks


def quote_blocks(text: str) -> list[dict]:
    """將長文字拆成多個 Quote Block。"""

    return [
        {
            "object": "block",
            "type": "quote",
            "quote": {
                "rich_text": _single_text_content(part),
            },
        }
        for part in _split_text(text)
    ]


def divider_block() -> dict:
    """建立分隔線。"""

    return {
        "object": "block",
        "type": "divider",
        "divider": {},
    }


def code_block(
    code: str,
    language: str = "plain text",
) -> dict:
    """建立程式碼 Block。"""

    supported_languages = {
        "abap",
        "arduino",
        "bash",
        "basic",
        "c",
        "clojure",
        "coffeescript",
        "c++",
        "c#",
        "css",
        "dart",
        "diff",
        "docker",
        "elixir",
        "elm",
        "erlang",
        "flow",
        "fortran",
        "f#",
        "gherkin",
        "glsl",
        "go",
        "graphql",
        "groovy",
        "haskell",
        "html",
        "java",
        "javascript",
        "json",
        "julia",
        "kotlin",
        "latex",
        "less",
        "lisp",
        "livescript",
        "lua",
        "makefile",
        "markdown",
        "markup",
        "matlab",
        "mermaid",
        "nix",
        "objective-c",
        "ocaml",
        "pascal",
        "perl",
        "php",
        "plain text",
        "powershell",
        "prolog",
        "protobuf",
        "python",
        "r",
        "reason",
        "ruby",
        "rust",
        "sass",
        "scala",
        "scheme",
        "scss",
        "shell",
        "sql",
        "swift",
        "toml",
        "typescript",
        "vb.net",
        "verilog",
        "vhdl",
        "visual basic",
        "webassembly",
        "xml",
        "yaml",
    }

    normalized_language = (language or "plain text").lower()

    if normalized_language not in supported_languages:
        normalized_language = "plain text"

    return {
        "object": "block",
        "type": "code",
        "code": {
            "rich_text": text_content(code),
            "language": normalized_language,
        },
    }


def toggle_block(
    title: str,
    children: list[dict] | None = None,
) -> dict:
    """建立 Toggle Block。"""

    toggle_data: dict[str, Any] = {
        "rich_text": text_content(title),
    }

    if children:
        toggle_data["children"] = children

    return {
        "object": "block",
        "type": "toggle",
        "toggle": toggle_data,
    }


def callout_block(
    title: str,
    content: str,
    icon: str = "💡",
    tone: str = "info",
) -> dict:
    """建立 Notion Callout Block。"""

    color_map = {
        "info": "blue_background",
        "warning": "yellow_background",
        "success": "green_background",
        "tip": "purple_background",
    }

    title_text = str(title or "").strip()
    content_text = str(content or "").strip()

    if title_text and content_text:
        callout_text = f"{title_text}\n{content_text}"
    else:
        callout_text = title_text or content_text

    return {
        "object": "block",
        "type": "callout",
        "callout": {
            "rich_text": text_content(callout_text),
            "icon": {
                "type": "emoji",
                "emoji": icon or "💡",
            },
            "color": color_map.get(tone, "blue_background"),
        },
    }


def table_row_block(values: list[str]) -> dict:
    """建立 Table Row。"""

    return {
        "object": "block",
        "type": "table_row",
        "table_row": {
            "cells": [
                text_content(str(value))
                for value in values
            ],
        },
    }


def table_block(
    headers: list[str],
    rows: list[list[str]],
) -> dict | None:
    """建立 Notion Table Block。"""

    if not headers:
        return None

    table_width = len(headers)
    normalized_rows = [headers]

    for row in rows:
        normalized_row = list(row[:table_width])

        while len(normalized_row) < table_width:
            normalized_row.append("")

        normalized_rows.append(normalized_row)

    return {
        "object": "block",
        "type": "table",
        "table": {
            "table_width": table_width,
            "has_column_header": True,
            "has_row_header": False,
            "children": [
                table_row_block(row)
                for row in normalized_rows
            ],
        },
    }


def _build_learning_objective_blocks(
    chapter_note: ChapterLearningNote,
) -> list[dict]:
    """建立學習目標區塊。"""

    if not chapter_note.learning_objectives:
        return []

    children = []

    for objective in chapter_note.learning_objectives:
        children.extend(bullet_blocks(objective))

    return [
        heading_block("🎯 學習目標", level=2),
        toggle_block(
            title="展開查看本章完成後能做到什麼",
            children=children,
        ),
    ]


def _build_callout_blocks(
    chapter_note: ChapterLearningNote,
) -> list[dict]:
    """建立重點標註區塊。"""

    if not chapter_note.callout_notes:
        return []

    blocks = [heading_block("✨ 重點標註", level=2)]

    for callout in chapter_note.callout_notes:
        blocks.append(
            callout_block(
                title=callout.title,
                content=callout.content,
                icon=callout.icon,
                tone=callout.tone,
            )
        )

    return blocks


def _build_key_point_blocks(
    chapter_note: ChapterLearningNote,
) -> list[dict]:
    """建立核心重點、術語與語法規則。"""

    blocks = []

    if chapter_note.key_points:
        blocks.append(heading_block("⭐ 核心重點", level=2))

        for point in chapter_note.key_points:
            blocks.extend(bullet_blocks(point))

    if chapter_note.important_terms:
        blocks.append(heading_block("📚 重要術語", level=2))

        for term in chapter_note.important_terms:
            blocks.extend(quote_blocks(term))

    if chapter_note.syntax_rules:
        blocks.append(
            heading_block("📌 語法規則與注意事項", level=2)
        )

        for rule in chapter_note.syntax_rules:
            blocks.extend(bullet_blocks(rule))

    return blocks


def _build_comparison_table_blocks(
    chapter_note: ChapterLearningNote,
) -> list[dict]:
    """建立比較表格區塊。"""

    if not chapter_note.comparison_tables:
        return []

    blocks = [heading_block("📊 重點比較表", level=2)]

    for table in chapter_note.comparison_tables:
        blocks.append(heading_block(table.title, level=3))

        notion_table = table_block(
            headers=table.headers,
            rows=table.rows,
        )

        if notion_table:
            blocks.append(notion_table)

        if table.note:
            blocks.extend(
                quote_blocks(f"補充：{table.note}")
            )

    return blocks


def _build_code_example_blocks(
    chapter_note: ChapterLearningNote,
) -> list[dict]:
    """建立程式碼範例區塊。"""

    if not chapter_note.code_examples:
        return []

    blocks = [heading_block("💻 程式碼範例", level=2)]

    for index, example in enumerate(
        chapter_note.code_examples,
        start=1,
    ):
        children = [
            code_block(
                code=example.code,
                language=example.language,
            )
        ]

        children.extend(paragraph_blocks(example.explanation))

        blocks.append(
            toggle_block(
                title=f"範例 {index}｜{example.title}",
                children=children,
            )
        )

    return blocks


def _build_mistake_blocks(
    chapter_note: ChapterLearningNote,
) -> list[dict]:
    """建立常見錯誤區塊。"""

    if not chapter_note.common_mistakes:
        return []

    blocks = [heading_block("⚠️ 常見錯誤與混淆", level=2)]

    for mistake in chapter_note.common_mistakes:
        blocks.append(
            callout_block(
                title=f"容易出錯：{mistake.mistake}",
                content=f"正確觀念：{mistake.correction}",
                icon="⚠️",
                tone="warning",
            )
        )

    return blocks


def _build_subsection_blocks(
    chapter_note: ChapterLearningNote,
) -> list[dict]:
    """建立子章節 Toggle。"""

    if not chapter_note.subsections:
        return []

    blocks = [heading_block("🧩 子章節整理", level=2)]

    for subsection in chapter_note.subsections:
        children = []

        children.extend(paragraph_blocks(subsection.summary))

        if subsection.key_points:
            children.append(paragraph_block("重點："))

            for point in subsection.key_points:
                children.extend(bullet_blocks(point))

        if subsection.important_terms:
            children.append(paragraph_block("術語："))

            for term in subsection.important_terms:
                children.extend(bullet_blocks(term))

        blocks.append(
            toggle_block(
                title=subsection.title,
                children=children,
            )
        )

    return blocks


def _build_image_insight_blocks(
    chapter_note: ChapterLearningNote,
) -> list[dict]:
    """
    建立 PDF 圖片解讀文字區塊。

    Base64 圖片目前不會上傳到 Notion，
    只會保留圖片分析文字。
    """

    if not chapter_note.image_insights:
        return []

    blocks = [
        heading_block("🖼️ PDF 圖片與畫面解讀", level=2)
    ]

    for image in chapter_note.image_insights:
        children = []

        children.extend(
            paragraph_blocks(f"圖片類型：{image.image_type}")
        )

        children.extend(paragraph_blocks(image.description))

        if image.related_subsection:
            children.append(
                callout_block(
                    title="對應子章節",
                    content=image.related_subsection,
                    icon="🔗",
                    tone="info",
                )
            )

        if image.learning_points:
            children.append(paragraph_block("從圖片可學到："))

            for point in image.learning_points:
                children.extend(bullet_blocks(point))

        blocks.append(
            toggle_block(
                title=f"第 {image.page_number} 頁｜{image.title}",
                children=children,
            )
        )

    return blocks


def _build_practice_tip_blocks(
    chapter_note: ChapterLearningNote,
) -> list[dict]:
    """建立練習建議區塊。"""

    if not chapter_note.practice_tips:
        return []

    blocks = [heading_block("🧪 練習建議", level=2)]

    for tip in chapter_note.practice_tips:
        children = []

        children.extend(
            paragraph_blocks(f"操作：{tip.instruction}")
        )

        if tip.expected_result:
            children.append(
                callout_block(
                    title="預期成果",
                    content=tip.expected_result,
                    icon="✅",
                    tone="success",
                )
            )

        blocks.append(
            toggle_block(
                title=tip.title,
                children=children,
            )
        )

    return blocks


def _build_mermaid_blocks(
    chapter_note: ChapterLearningNote,
) -> list[dict]:
    """建立 Mermaid 學習地圖。"""

    if not chapter_note.mermaid.strip():
        return []

    return [
        heading_block("🗺️ 章節學習地圖", level=2),
        code_block(
            code=chapter_note.mermaid,
            language="mermaid",
        ),
    ]


def _build_quiz_blocks(
    chapter_note: ChapterLearningNote,
) -> list[dict]:
    """建立 Quiz Toggle。"""

    if not chapter_note.quiz:
        return []

    blocks = [heading_block("❓ 章節 Quiz", level=2)]

    for index, quiz_item in enumerate(
        chapter_note.quiz,
        start=1,
    ):
        children = []

        children.extend(
            paragraph_blocks(f"答案：{quiz_item.answer}")
        )

        if quiz_item.explanation:
            children.extend(
                paragraph_blocks(
                    f"說明：{quiz_item.explanation}"
                )
            )

        blocks.append(
            toggle_block(
                title=f"第 {index} 題｜{quiz_item.question}",
                children=children,
            )
        )

    return blocks


def _build_flashcard_blocks(
    chapter_note: ChapterLearningNote,
) -> list[dict]:
    """建立 Flash Card Toggle。"""

    if not chapter_note.flashcards:
        return []

    blocks = [heading_block("🗂️ 章節 Flash Cards", level=2)]

    for index, card in enumerate(
        chapter_note.flashcards,
        start=1,
    ):
        blocks.append(
            toggle_block(
                title=f"Flash Card {index}｜{card.front}",
                children=paragraph_blocks(card.back),
            )
        )

    return blocks


def build_chapter_notion_blocks(
    chapter_note: ChapterLearningNote,
) -> list[dict]:
    """把 ChapterLearningNote 轉成安全的 Notion Blocks。"""

    blocks = [
        callout_block(
            title="📘 本章摘要",
            content=chapter_note.chapter_summary,
            icon="📘",
            tone="info",
        ),
        heading_block("🧠 白話講解", level=2),
    ]

    blocks.extend(paragraph_blocks(chapter_note.plain_explanation))
    blocks.append(divider_block())

    blocks.extend(_build_learning_objective_blocks(chapter_note))
    blocks.extend(_build_callout_blocks(chapter_note))
    blocks.extend(_build_key_point_blocks(chapter_note))
    blocks.extend(_build_comparison_table_blocks(chapter_note))
    blocks.extend(_build_code_example_blocks(chapter_note))
    blocks.extend(_build_mistake_blocks(chapter_note))
    blocks.extend(_build_subsection_blocks(chapter_note))
    blocks.extend(_build_image_insight_blocks(chapter_note))
    blocks.extend(_build_practice_tip_blocks(chapter_note))
    blocks.extend(_build_mermaid_blocks(chapter_note))
    blocks.extend(_build_quiz_blocks(chapter_note))
    blocks.extend(_build_flashcard_blocks(chapter_note))

    return blocks


def _append_blocks_in_batches(
    client: Client,
    page_id: str,
    blocks: list[dict],
) -> None:
    """分批附加 Block。"""

    for start_index in range(
        0,
        len(blocks),
        MAX_BLOCKS_PER_REQUEST,
    ):
        batch = blocks[
            start_index:start_index + MAX_BLOCKS_PER_REQUEST
        ]

        client.blocks.children.append(
            block_id=page_id,
            children=batch,
        )


def _create_page(
    client: Client,
    parent_page_id: str,
    title: str,
) -> dict:
    """在指定 Notion 頁面下建立子頁。"""

    return client.pages.create(
        parent={
            "type": "page_id",
            "page_id": parent_page_id,
        },
        properties={
            "title": {
                "title": text_content(title),
            }
        },
    )


def create_chapter_notion_page(
    chapter_note: ChapterLearningNote,
    parent_page_id: str | None = None,
) -> str:
    """建立單一 Module 的 Notion 詳細學習筆記頁面。"""

    target_parent_page_id = parent_page_id or NOTION_PARENT_PAGE_ID

    if not target_parent_page_id:
        raise ValueError(
            "找不到 NOTION_PARENT_PAGE_ID，請確認 .env 設定。"
        )

    client = get_notion_client()

    page_response = _create_page(
        client=client,
        parent_page_id=target_parent_page_id,
        title=chapter_note.chapter_title,
    )

    blocks = build_chapter_notion_blocks(chapter_note)

    if blocks:
        _append_blocks_in_batches(
            client=client,
            page_id=page_response["id"],
            blocks=blocks,
        )

    return page_response["url"]


def _create_document_parent_page(
    document_name: str,
    chapter_count: int,
) -> dict:
    """建立整份文件的 Notion 父頁。"""

    if not NOTION_PARENT_PAGE_ID:
        raise ValueError(
            "找不到 NOTION_PARENT_PAGE_ID，請確認 .env 設定。"
        )

    client = get_notion_client()

    document_title = Path(document_name).stem
    page_title = f"{document_title}｜詳細學習筆記"

    parent_page = _create_page(
        client=client,
        parent_page_id=NOTION_PARENT_PAGE_ID,
        title=page_title,
    )

    overview_blocks = [
        callout_block(
            title="📘 文件詳細學習筆記",
            content=(
                f"原始文件：{document_name}\n"
                f"偵測主章節數：{chapter_count}\n"
                "每個 Module 已建立為本頁下方的子頁面。"
            ),
            icon="📘",
            tone="info",
        ),
        heading_block("📚 章節總覽", level=2),
        paragraph_block(
            "請從本頁下方開啟各個 Module 子頁面，"
            "閱讀完整學習筆記。"
        ),
    ]

    _append_blocks_in_batches(
        client=client,
        page_id=parent_page["id"],
        blocks=overview_blocks,
    )

    return parent_page


def _append_export_summary(
    parent_page_id: str,
    completed_chapters: list[dict],
    failed_chapters: list[dict],
) -> None:
    """在父頁最後附加本次匯出結果。"""

    client = get_notion_client()

    blocks = [
        divider_block(),
        heading_block("✅ 匯出結果", level=2),
        paragraph_block(
            f"成功建立 {len(completed_chapters)} 個 Module 子頁面。"
        ),
    ]

    if failed_chapters:
        blocks.append(
            callout_block(
                title="⚠️ 尚有未完成章節",
                content=(
                    f"目前有 {len(failed_chapters)} 個 Module 尚未成功匯出。"
                    "再次按下繼續匯出時，系統只會補跑未完成的章節。"
                ),
                icon="⚠️",
                tone="warning",
            )
        )
    else:
        blocks.append(
            callout_block(
                title="🎉 全部章節已完成",
                content="所有 Module 都已成功建立為 Notion 詳細學習筆記。",
                icon="✅",
                tone="success",
            )
        )

    _append_blocks_in_batches(
        client=client,
        page_id=parent_page_id,
        blocks=blocks,
    )


def _get_or_generate_visual_context(
    document_name: str,
    chapter: dict,
    parsed_document: dict,
    progress_callback: Callable[[int, int, str], None] | None,
    current: int,
    total: int,
    max_visual_pages: int,
) -> tuple[list[dict], bool]:
    """
    優先讀取 PDF 視覺分析快取。

    回傳：
    - visual_context
    - 是否使用快取
    """

    chapter_cache = load_chapter_cache(
        document_name=document_name,
        chapter=chapter,
    )

    if chapter_cache["visual_cached"]:
        return chapter_cache["visual_context"], True

    metadata = parsed_document.get("metadata", {})

    is_pdf = metadata.get("file_extension") == ".pdf"
    pdf_bytes = parsed_document.get("pdf_bytes")
    page_texts = parsed_document.get("page_texts")

    if not is_pdf or not pdf_bytes or not page_texts:
        save_visual_context_cache(
            document_name=document_name,
            chapter=chapter,
            visual_context=[],
        )

        return [], False

    if progress_callback:
        progress_callback(
            current,
            total,
            f"正在辨識 PDF 圖片：{chapter.get('title', '未命名章節')}",
        )

    visual_context = analyze_chapter_visuals(
        chapter=chapter,
        pdf_bytes=pdf_bytes,
        page_texts=page_texts,
        max_pages=max_visual_pages,
    )

    save_visual_context_cache(
        document_name=document_name,
        chapter=chapter,
        visual_context=visual_context,
    )

    return visual_context, False


def _get_or_generate_chapter_note(
    document_name: str,
    chapter: dict,
    visual_context: list[dict],
    progress_callback: Callable[[int, int, str], None] | None,
    current: int,
    total: int,
) -> tuple[ChapterLearningNote, bool]:
    """
    優先讀取 AI 詳細學習筆記快取。

    回傳：
    - ChapterLearningNote
    - 是否使用快取
    """

    chapter_cache = load_chapter_cache(
        document_name=document_name,
        chapter=chapter,
    )

    if chapter_cache["note_cached"]:
        return chapter_cache["chapter_note"], True

    if progress_callback:
        progress_callback(
            current,
            total,
            f"正在生成詳細筆記：{chapter.get('title', '未命名章節')}",
        )

    chapter_note = analyze_chapter(
        chapter=chapter,
        visual_context=visual_context,
    )

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
    progress_callback: Callable[[int, int, str], None] | None = None,
    max_visual_pages: int = 3,
    resume: bool = True,
) -> dict:
    """
    一鍵建立或繼續整份文件的 Notion 詳細學習筆記。

    resume=True：
    - 讀取既有 Notion 匯出進度。
    - 跳過已成功建立的 Module。
    - 讀取既有 AI 詳細筆記快取。
    - 未完成的 Module 優先直接匯出快取結果。

    resume=False：
    - 建立新的 Notion 父頁。
    - 仍可沿用 AI 詳細筆記快取，避免重複花 API 額度。
    """

    if not chapters:
        raise ValueError("找不到可匯出的主章節。")

    chapter_count = len(chapters)

    if resume:
        state = load_export_state(
            document_name=document_name,
            chapter_count=chapter_count,
        )
    else:
        state = reset_export_state(
            document_name=document_name,
            chapter_count=chapter_count,
        )

    parent_page_id = state.get("parent_page_id", "")
    parent_page_url = state.get("parent_page_url", "")

    if not parent_page_id or not parent_page_url:
        parent_page = _create_document_parent_page(
            document_name=document_name,
            chapter_count=chapter_count,
        )

        parent_page_id = parent_page["id"]
        parent_page_url = parent_page["url"]

        state = set_parent_page(
            document_name=document_name,
            state=state,
            parent_page_id=parent_page_id,
            parent_page_url=parent_page_url,
        )

    pending_chapters = get_pending_chapters(
        chapters=chapters,
        state=state,
    )

    total_pending = len(pending_chapters)
    completed_before = len(state.get("completed_chapters", {}))

    if total_pending == 0:
        if not state.get("is_finished", False):
            state = mark_export_finished(
                document_name=document_name,
                state=state,
            )

            _append_export_summary(
                parent_page_id=parent_page_id,
                completed_chapters=list(
                    state["completed_chapters"].values()
                ),
                failed_chapters=list(
                    state["failed_chapters"].values()
                ),
            )

        return {
            "parent_page_url": parent_page_url,
            "completed_chapters": list(
                state["completed_chapters"].values()
            ),
            "failed_chapters": list(
                state["failed_chapters"].values()
            ),
            "skipped_chapter_count": completed_before,
            "processed_chapter_count": 0,
            "cached_visual_count": 0,
            "cached_note_count": 0,
            "is_finished": state.get("is_finished", False),
        }

    cached_visual_count = 0
    cached_note_count = 0

    for pending_index, chapter in enumerate(
        pending_chapters,
        start=1,
    ):
        chapter_id = chapter.get("chapter_id")
        chapter_title = chapter.get(
            "title",
            f"第 {pending_index} 章",
        )

        overall_current = completed_before + pending_index
        overall_total = chapter_count

        try:
            if progress_callback:
                progress_callback(
                    overall_current - 1,
                    overall_total,
                    f"正在準備：{chapter_title}",
                )

            visual_context, visual_from_cache = (
                _get_or_generate_visual_context(
                    document_name=document_name,
                    chapter=chapter,
                    parsed_document=parsed_document,
                    progress_callback=progress_callback,
                    current=overall_current - 1,
                    total=overall_total,
                    max_visual_pages=max_visual_pages,
                )
            )

            if visual_from_cache:
                cached_visual_count += 1

                if progress_callback:
                    progress_callback(
                        overall_current - 1,
                        overall_total,
                        f"已讀取圖片分析快取：{chapter_title}",
                    )

            chapter_note, note_from_cache = (
                _get_or_generate_chapter_note(
                    document_name=document_name,
                    chapter=chapter,
                    visual_context=visual_context,
                    progress_callback=progress_callback,
                    current=overall_current - 1,
                    total=overall_total,
                )
            )

            if note_from_cache:
                cached_note_count += 1

                if progress_callback:
                    progress_callback(
                        overall_current - 1,
                        overall_total,
                        f"已讀取詳細筆記快取：{chapter_title}",
                    )

            if progress_callback:
                progress_callback(
                    overall_current - 1,
                    overall_total,
                    f"正在建立 Notion 子頁：{chapter_title}",
                )

            chapter_url = create_chapter_notion_page(
                chapter_note=chapter_note,
                parent_page_id=parent_page_id,
            )

            state = mark_chapter_completed(
                document_name=document_name,
                state=state,
                chapter_id=chapter_id,
                chapter_title=chapter_title,
                notion_url=chapter_url,
            )

        except Exception as error:
            state = mark_chapter_failed(
                document_name=document_name,
                state=state,
                chapter_id=chapter_id,
                chapter_title=chapter_title,
                error_message=str(error),
            )

        if progress_callback:
            progress_callback(
                overall_current,
                overall_total,
                f"已處理 {overall_current} / {overall_total} 個主章節。",
            )

    completed_chapters = list(
        state.get("completed_chapters", {}).values()
    )

    failed_chapters = list(
        state.get("failed_chapters", {}).values()
    )

    is_finished = (
        len(completed_chapters) == chapter_count
        and len(failed_chapters) == 0
    )

    if is_finished:
        state = mark_export_finished(
            document_name=document_name,
            state=state,
        )

    _append_export_summary(
        parent_page_id=parent_page_id,
        completed_chapters=completed_chapters,
        failed_chapters=failed_chapters,
    )

    return {
        "parent_page_url": parent_page_url,
        "completed_chapters": completed_chapters,
        "failed_chapters": failed_chapters,
        "skipped_chapter_count": completed_before,
        "processed_chapter_count": total_pending,
        "cached_visual_count": cached_visual_count,
        "cached_note_count": cached_note_count,
        "is_finished": is_finished,
    }