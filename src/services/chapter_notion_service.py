import base64
import inspect
import mimetypes
import re

import requests
from datetime import datetime
from typing import Callable, Optional

from notion_client import Client
from sqlalchemy import select


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
from src.database.database import get_database_session
from src.database.models import Document
from src.services.learning_database_service import (
    count_chapter_learning_items,
    save_chapter_learning_items,
)


MAX_RICH_TEXT_LENGTH = 1800
MAX_BLOCKS_PER_REQUEST = 80


NOTION_API_VERSION = "2026-03-11"
MAX_NOTION_IMAGE_BYTES = 20 * 1024 * 1024


def _toggle(
    title: str,
    children: list[dict],
) -> dict:
    """建立 Notion 原生摺疊區塊。"""

    safe_children = list(children or [])

    if not safe_children:
        safe_children = _paragraph(
            "目前沒有內容。"
        )

    return {
        "object": "block",
        "type": "toggle",
        "toggle": {
            "rich_text": _rich_text(
                title
            ),
            "children": safe_children,
        },
    }


def _decode_image_data_url(
    data_url: str,
) -> tuple[bytes, str, str]:
    """
    解析 data URL。

    回傳：
    - 圖片 bytes
    - MIME type
    - 建議副檔名
    """

    if not isinstance(
        data_url,
        str,
    ):
        raise ValueError(
            "圖片資料不是字串。"
        )

    match = re.match(
        r"^data:"
        r"(?P<mime>image/[a-zA-Z0-9.+-]+)"
        r";base64,"
        r"(?P<data>.+)$",
        data_url,
        flags=re.DOTALL,
    )

    if not match:
        raise ValueError(
            "圖片不是有效的 Base64 data URL。"
        )

    mime_type = match.group(
        "mime"
    ).lower()

    image_bytes = base64.b64decode(
        match.group("data"),
        validate=False,
    )

    if not image_bytes:
        raise ValueError(
            "圖片內容是空的。"
        )

    if len(image_bytes) > MAX_NOTION_IMAGE_BYTES:
        raise ValueError(
            "圖片超過 Notion 單檔上傳限制。"
        )

    extension = (
        mimetypes.guess_extension(
            mime_type
        )
        or ".png"
    )

    if extension == ".jpe":
        extension = ".jpg"

    return (
        image_bytes,
        mime_type,
        extension,
    )


def _create_notion_file_upload(
    filename: str,
    content_type: str,
) -> dict:
    """建立 Notion 單檔上傳工作。"""

    if not NOTION_API_KEY:
        raise ValueError(
            "尚未設定 NOTION_API_KEY。"
        )

    response = requests.post(
        "https://api.notion.com/v1/file_uploads",
        headers={
            "Authorization": (
                f"Bearer {NOTION_API_KEY}"
            ),
            "Notion-Version": (
                NOTION_API_VERSION
            ),
            "Content-Type": (
                "application/json"
            ),
        },
        json={
            "mode": "single_part",
            "filename": filename,
            "content_type": content_type,
        },
        timeout=60,
    )

    response.raise_for_status()

    result = response.json()

    if not result.get("id"):
        raise ValueError(
            "Notion 沒有回傳 file_upload ID。"
        )

    return result


def _send_notion_file_upload(
    upload_info: dict,
    filename: str,
    content_type: str,
    file_bytes: bytes,
) -> str:
    """將圖片 bytes 傳送至 Notion。"""

    file_upload_id = str(
        upload_info.get("id")
        or ""
    ).strip()

    upload_url = str(
        upload_info.get("upload_url")
        or (
            "https://api.notion.com/v1/"
            f"file_uploads/{file_upload_id}/send"
        )
    ).strip()

    if not file_upload_id:
        raise ValueError(
            "缺少 Notion file_upload ID。"
        )

    response = requests.post(
        upload_url,
        headers={
            "Authorization": (
                f"Bearer {NOTION_API_KEY}"
            ),
            "Notion-Version": (
                NOTION_API_VERSION
            ),
        },
        files={
            "file": (
                filename,
                file_bytes,
                content_type,
            )
        },
        timeout=120,
    )

    response.raise_for_status()

    return file_upload_id


def _upload_data_url_to_notion(
    data_url: str,
    filename_stem: str,
) -> str:
    """上傳 Base64 圖片並回傳 file_upload ID。"""

    (
        image_bytes,
        content_type,
        extension,
    ) = _decode_image_data_url(
        data_url
    )

    safe_stem = re.sub(
        r"[^a-zA-Z0-9_-]+",
        "_",
        filename_stem,
    ).strip("_")

    if not safe_stem:
        safe_stem = "chapter_image"

    filename = (
        f"{safe_stem}{extension}"
    )

    upload_info = (
        _create_notion_file_upload(
            filename=filename,
            content_type=content_type,
        )
    )

    return _send_notion_file_upload(
        upload_info=upload_info,
        filename=filename,
        content_type=content_type,
        file_bytes=image_bytes,
    )


def _image_file_upload_block(
    file_upload_id: str,
    caption: str = "",
) -> dict:
    """建立使用 Notion file_upload 的圖片區塊。"""

    image_data = {
        "type": "file_upload",
        "file_upload": {
            "id": file_upload_id,
        },
    }

    if caption:
        image_data["caption"] = (
            _rich_text(caption)
        )

    return {
        "object": "block",
        "type": "image",
        "image": image_data,
    }


def _find_visual_image_data_url(
    item: dict,
) -> str:
    """相容不同 visual_context 圖片欄位名稱。"""

    if not isinstance(item, dict):
        return ""

    for key in (
        "image_data_url",
        "data_url",
        "image_base64",
        "page_image_data_url",
    ):
        value = item.get(key)

        if (
            isinstance(value, str)
            and value.strip()
        ):
            if value.startswith(
                "data:image/"
            ):
                return value.strip()

            if key == "image_base64":
                return (
                    "data:image/png;base64,"
                    f"{value.strip()}"
                )

    return ""


def _build_visual_image_blocks(
    visual_context: list[dict],
    chapter_id: str,
) -> tuple[list[dict], list[str]]:
    """
    將 PDF 視覺內容上傳至 Notion 並建立圖片 blocks。

    回傳：
    - image blocks
    - 無法上傳的錯誤訊息
    """

    blocks: list[dict] = []
    errors: list[str] = []
    seen_images: set[str] = set()

    for index, item in enumerate(
        visual_context or [],
        start=1,
    ):
        if not isinstance(item, dict):
            continue

        data_url = (
            _find_visual_image_data_url(
                item
            )
        )

        if not data_url:
            continue

        image_identity = data_url[
            :120
        ] + str(len(data_url))

        if image_identity in seen_images:
            continue

        seen_images.add(
            image_identity
        )

        page_number = (
            item.get("page_number")
            or item.get("page")
            or index
        )

        title = str(
            item.get("title")
            or item.get("description")
            or f"第 {page_number} 頁圖片"
        ).strip()

        caption = (
            f"第 {page_number} 頁｜"
            f"{title}"
        )

        try:
            file_upload_id = (
                _upload_data_url_to_notion(
                    data_url=data_url,
                    filename_stem=(
                        f"module_{chapter_id}_"
                        f"page_{page_number}"
                    ),
                )
            )

            blocks.append(
                _image_file_upload_block(
                    file_upload_id=(
                        file_upload_id
                    ),
                    caption=caption,
                )
            )

        except Exception as error:
            errors.append(
                f"第 {page_number} 頁圖片："
                f"{error}"
            )

    return blocks, errors



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


def _callout(
    text: str,
    icon: str = "💡",
    color: str = "blue_background",
) -> dict:
    """建立帶顏色的 Notion callout block。"""

    return {
        "object": "block",
        "type": "callout",
        "callout": {
            "rich_text": _rich_text(text),
            "icon": {
                "type": "emoji",
                "emoji": icon,
            },
            "color": color,
        },
    }


def _quote(text: str) -> list[dict]:
    """建立 quote blocks。"""

    blocks = []

    for part in _chunk_text(text):
        blocks.append(
            {
                "object": "block",
                "type": "quote",
                "quote": {
                    "rich_text": _rich_text(part),
                },
            }
        )

    return blocks


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



def _build_parent_page_blocks(
    document_name: str,
    chapter_count: int,
) -> list[dict]:
    """建立與參考 Notion 相同風格的父頁內容。"""

    blocks = [
        _callout(
            (
                "📘 文件詳細學習筆記\n"
                f"原始文件：{document_name}\n"
                f"偵測主章節數：{chapter_count}\n"
                "每個主章節已建立為本頁下方的子頁面。"
            ),
            icon="📘",
            color="blue_background",
        ),
        _heading_2("📚 章節總覽"),
    ]

    blocks.extend(
        _paragraph(
            "請從本頁下方開啟各個主章節子頁面，"
            "閱讀完整學習筆記。"
        )
    )

    blocks.append(_divider())

    return blocks


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


def _build_quiz_blocks(
    quiz_items: list[ChapterQuizItem],
) -> list[dict]:
    """建立可摺疊的 Quiz blocks。"""

    blocks = []

    if not quiz_items:
        blocks.extend(
            _paragraph(
                "本章未產生 Quiz。"
            )
        )
        return blocks

    for index, item in enumerate(
        quiz_items,
        start=1,
    ):
        question = str(
            item.question or ""
        ).strip()

        answer = str(
            item.answer or ""
        ).strip()

        explanation = str(
            item.explanation or ""
        ).strip()

        children = []

        children.append(
            _heading_3("標準答案")
        )

        children.extend(
            _paragraph(
                answer
                or "本題沒有標準答案。"
            )
        )

        if explanation:
            children.append(
                _heading_3("答案解析")
            )

            children.extend(
                _paragraph(
                    explanation
                )
            )

        blocks.append(
            _toggle(
                title=(
                    f"第 {index} 題｜"
                    f"{question}"
                ),
                children=children,
            )
        )

    return blocks


def _build_flashcard_blocks(
    flashcards: list[ChapterFlashcardItem],
) -> list[dict]:
    """建立可摺疊的 Flash Card blocks。"""

    blocks = []

    if not flashcards:
        blocks.extend(
            _paragraph(
                "本章未產生 Flash Cards。"
            )
        )
        return blocks

    for index, card in enumerate(
        flashcards,
        start=1,
    ):
        front = str(
            card.front or ""
        ).strip()

        back = str(
            card.back or ""
        ).strip()

        children = []

        children.append(
            _heading_3("背面答案")
        )

        children.extend(
            _paragraph(
                back
                or "這張卡片沒有背面內容。"
            )
        )

        blocks.append(
            _toggle(
                title=(
                    f"Flash Card {index}｜"
                    f"{front}"
                ),
                children=children,
            )
        )

    return blocks


def _build_chapter_note_blocks(
    chapter_note: ChapterLearningNote,
    visual_context: list[dict] | None = None,
    chapter_id: str = "",
) -> tuple[list[dict], list[str]]:
    """
    建立與參考 Notion 相同風格的詳細學習筆記。

    版型：
    - 摘要 Callout
    - 白話講解
    - 摺疊學習目標
    - 彩色重點 Callout
    - 核心重點
    - 引用式重要術語
    - 語法規則
    - 比較表
    - 摺疊程式碼範例
    - 警告 Callout
    - 子章節
    - PDF 圖片
    - 練習
    - Mermaid
    - 摺疊 Quiz / Flash Cards
    """

    is_valid, reason = is_valid_chapter_note(
        chapter_note
    )

    if not is_valid:
        raise ValueError(
            f"拒絕建立空白 Notion 子頁：{reason}"
        )

    blocks: list[dict] = []

    summary_text = (
        chapter_note.chapter_summary
        or "本章未產生摘要。"
    )

    blocks.append(
        _callout(
            (
                "📘 本章摘要\n"
                f"{summary_text}"
            ),
            icon="📘",
            color="blue_background",
        )
    )

    blocks.append(
        _heading_2("🧠 白話講解")
    )

    blocks.extend(
        _paragraph(
            chapter_note.plain_explanation
            or "本章未產生白話講解。"
        )
    )

    blocks.append(_divider())

    objective_children: list[dict] = []

    for objective in (
        chapter_note.learning_objectives
        or []
    ):
        objective_children.extend(
            _bulleted_item(objective)
        )

    blocks.append(
        _heading_2("🎯 學習目標")
    )

    blocks.append(
        _toggle(
            title="展開查看本章完成後能做到什麼",
            children=(
                objective_children
                or _paragraph(
                    "本章未產生明確學習目標。"
                )
            ),
        )
    )

    blocks.append(
        _heading_2("🗺️ 章節學習地圖")
    )

    if chapter_note.mermaid:
        blocks.append(
            _code_block(
                code=chapter_note.mermaid,
                language="plain text",
            )
        )
    else:
        blocks.extend(
            _paragraph(
                "本章未產生 Mermaid 學習地圖。"
            )
        )

    if chapter_note.callout_notes:
        blocks.append(
            _heading_2("✨ 重點標註")
        )

        callout_color_map = {
            "⚠️": "yellow_background",
            "❗": "red_background",
            "✅": "green_background",
            "📌": "purple_background",
            "💡": "blue_background",
            "📝": "gray_background",
        }

        for callout_note in (
            chapter_note.callout_notes
        ):
            title = (
                callout_note.title
                or "補充提醒"
            )

            content = (
                callout_note.content
                or ""
            )

            icon = (
                callout_note.icon
                or "💡"
            )

            color = callout_color_map.get(
                icon,
                "blue_background",
            )

            blocks.append(
                _callout(
                    (
                        f"{title}\n"
                        f"{content}"
                    ),
                    icon=icon,
                    color=color,
                )
            )

    blocks.append(
        _heading_2("⭐ 核心重點")
    )

    if chapter_note.key_points:
        for point in chapter_note.key_points:
            blocks.extend(
                _bulleted_item(point)
            )
    else:
        blocks.extend(
            _paragraph(
                "本章未產生核心重點。"
            )
        )

    blocks.append(
        _heading_2("📚 重要術語")
    )

    if chapter_note.important_terms:
        for term in (
            chapter_note.important_terms
        ):
            blocks.extend(
                _quote(str(term))
            )
    else:
        blocks.extend(
            _paragraph(
                "本章未產生重要術語。"
            )
        )

    blocks.append(
        _heading_2("📌 語法規則與注意事項")
    )

    if chapter_note.syntax_rules:
        for rule in (
            chapter_note.syntax_rules
        ):
            blocks.extend(
                _bulleted_item(rule)
            )
    else:
        blocks.extend(
            _paragraph(
                "本章未產生語法規則。"
            )
        )

    if chapter_note.comparison_tables:
        blocks.append(
            _heading_2("📊 重點比較表")
        )

        for table in (
            chapter_note.comparison_tables
        ):
            blocks.append(
                _heading_3(table.title)
            )

            table_block = _table_block(
                headers=table.headers,
                rows=table.rows,
            )

            if table_block:
                blocks.append(table_block)

            if table.note:
                blocks.extend(
                    _quote(
                        f"補充：{table.note}"
                    )
                )

    blocks.append(
        _heading_2("💻 程式碼範例")
    )

    if chapter_note.code_examples:
        for index, example in enumerate(
            chapter_note.code_examples,
            start=1,
        ):
            example_children = [
                _code_block(
                    code=example.code,
                    language=(
                        example.language
                        or "plain text"
                    ),
                )
            ]

            example_children.extend(
                _paragraph(
                    example.explanation
                    or "本範例沒有補充說明。"
                )
            )

            blocks.append(
                _toggle(
                    title=(
                        f"範例 {index}｜"
                        f"{example.title}"
                    ),
                    children=example_children,
                )
            )
    else:
        blocks.extend(
            _paragraph(
                "本章未產生程式碼範例。"
            )
        )

    blocks.append(
        _heading_2("⚠️ 常見錯誤與混淆")
    )

    if chapter_note.common_mistakes:
        for mistake in (
            chapter_note.common_mistakes
        ):
            blocks.append(
                _callout(
                    (
                        f"容易出錯：{mistake.mistake}\n"
                        f"正確觀念：{mistake.correction}"
                    ),
                    icon="⚠️",
                    color="yellow_background",
                )
            )
    else:
        blocks.extend(
            _paragraph(
                "本章未產生常見錯誤提醒。"
            )
        )

    blocks.append(
        _heading_2("🧩 子章節整理")
    )

    if chapter_note.subsections:
        for subsection in (
            chapter_note.subsections
        ):
            blocks.append(
                _heading_3(
                    subsection.title
                )
            )

            blocks.extend(
                _paragraph(
                    subsection.summary
                )
            )

            for point in (
                subsection.key_points
                or []
            ):
                blocks.extend(
                    _bulleted_item(point)
                )

            for term in (
                subsection.important_terms
                or []
            ):
                blocks.extend(
                    _quote(str(term))
                )
    else:
        blocks.extend(
            _paragraph(
                "本章未產生子章節整理。"
            )
        )

    blocks.append(
        _heading_2("🖼️ PDF 圖片與畫面解讀")
    )

    (
        visual_image_blocks,
        visual_upload_errors,
    ) = _build_visual_image_blocks(
        visual_context=(
            visual_context or []
        ),
        chapter_id=str(
            chapter_id or "unknown"
        ),
    )

    if visual_image_blocks:
        blocks.extend(
            visual_image_blocks
        )

    if chapter_note.image_insights:
        for image in (
            chapter_note.image_insights
        ):
            image_children: list[dict] = []

            image_children.extend(
                _paragraph(
                    f"圖片類型：{image.image_type}"
                )
            )

            image_children.extend(
                _paragraph(
                    image.description
                )
            )

            if image.related_subsection:
                image_children.extend(
                    _paragraph(
                        "對應子章節："
                        f"{image.related_subsection}"
                    )
                )

            for point in (
                image.learning_points
                or []
            ):
                image_children.extend(
                    _bulleted_item(point)
                )

            blocks.append(
                _toggle(
                    title=(
                        f"第 {image.page_number} 頁｜"
                        f"{image.title}"
                    ),
                    children=image_children,
                )
            )
    elif not visual_image_blocks:
        blocks.extend(
            _paragraph(
                "本章未產生 PDF 視覺補充。"
            )
        )

    blocks.append(
        _heading_2("🧪 練習建議")
    )

    if chapter_note.practice_tips:
        for index, tip in enumerate(
            chapter_note.practice_tips,
            start=1,
        ):
            tip_children = []

            tip_children.extend(
                _paragraph(
                    f"操作：{tip.instruction}"
                )
            )

            if tip.expected_result:
                tip_children.extend(
                    _paragraph(
                        "預期成果："
                        f"{tip.expected_result}"
                    )
                )

            blocks.append(
                _toggle(
                    title=(
                        f"練習 {index}｜"
                        f"{tip.title}"
                    ),
                    children=tip_children,
                )
            )
    else:
        blocks.extend(
            _paragraph(
                "本章未產生練習建議。"
            )
        )

    blocks.append(
        _heading_2("❓ 章節 Quiz")
    )

    blocks.extend(
        _build_quiz_blocks(
            chapter_note.quiz
        )
    )

    blocks.append(
        _heading_2("🗂️ 章節 Flash Cards")
    )

    blocks.extend(
        _build_flashcard_blocks(
            chapter_note.flashcards
        )
    )

    return blocks, visual_upload_errors


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



def _resolve_document_id(
    document_name: str,
    document_id: str | int | None = None,
) -> str | int | None:
    """取得 SQLite 文件 ID。"""

    if document_id:
        return document_id

    with get_database_session() as session:
        statement = (
            select(Document)
            .where(Document.file_name == document_name)
            .order_by(Document.updated_at.desc())
        )

        document = session.execute(
            statement
        ).scalars().first()

        return document.id if document else None


def _sync_chapter_note_to_sqlite(
    document_id: str | int | None,
    chapter_id: str,
    chapter_note: ChapterLearningNote,
    force: bool = False,
) -> dict:
    """將章節 Quiz / Flash Cards 同步到 SQLite。"""

    if not document_id:
        return {
            "synced": False,
            "skipped": True,
            "reason": "找不到 SQLite 文件 ID",
            "quiz_count": 0,
            "flashcard_count": 0,
        }

    counts = count_chapter_learning_items(
        document_id=document_id,
        source_chapter_id=str(chapter_id),
    )

    quiz_count = int(
        counts.get("quiz_count", 0) or 0
    )

    flashcard_count = int(
        counts.get("flashcard_count", 0) or 0
    )

    if (
        not force
        and (
            quiz_count > 0
            or flashcard_count > 0
        )
    ):
        return {
            "synced": False,
            "skipped": True,
            "reason": "SQLite 已有學習資料，避免覆蓋既有作答紀錄",
            "quiz_count": quiz_count,
            "flashcard_count": flashcard_count,
        }

    result = save_chapter_learning_items(
        document_id=document_id,
        source_chapter_id=str(chapter_id),
        chapter_note=chapter_note,
    )

    return {
        "synced": bool(result.get("saved")),
        "skipped": False,
        "reason": result.get("reason", ""),
        "quiz_count": int(
            result.get("quiz_count", 0) or 0
        ),
        "flashcard_count": int(
            result.get("flashcard_count", 0) or 0
        ),
    }


def _sync_cached_notes_to_sqlite(
    document_name: str,
    document_id: str | int | None,
    chapters: list[dict],
) -> dict:
    """將有效快取補寫到 SQLite。"""

    summary = {
        "synced_chapter_count": 0,
        "skipped_chapter_count": 0,
        "failed_chapter_count": 0,
        "synced_quiz_count": 0,
        "synced_flashcard_count": 0,
        "errors": [],
    }

    if not document_id:
        summary["errors"].append(
            "找不到 SQLite 文件 ID"
        )
        return summary

    for index, chapter in enumerate(
        chapters,
        start=1,
    ):
        chapter_id = str(
            chapter.get("chapter_id")
            or index
        )

        try:
            cached_data = load_chapter_cache(
                document_name=document_name,
                chapter=chapter,
            )

            chapter_note = cached_data.get(
                "chapter_note"
            )

            if (
                not cached_data.get("note_cached")
                or not cached_data.get("note_cache_valid")
                or chapter_note is None
            ):
                summary[
                    "skipped_chapter_count"
                ] += 1
                continue

            result = _sync_chapter_note_to_sqlite(
                document_id=document_id,
                chapter_id=chapter_id,
                chapter_note=chapter_note,
                force=False,
            )

            if result.get("synced"):
                summary[
                    "synced_chapter_count"
                ] += 1
                summary[
                    "synced_quiz_count"
                ] += int(
                    result.get(
                        "quiz_count",
                        0,
                    )
                    or 0
                )
                summary[
                    "synced_flashcard_count"
                ] += int(
                    result.get(
                        "flashcard_count",
                        0,
                    )
                    or 0
                )
            elif result.get("skipped"):
                summary[
                    "skipped_chapter_count"
                ] += 1
            else:
                summary[
                    "failed_chapter_count"
                ] += 1
                summary["errors"].append(
                    f"Module {chapter_id}："
                    f"{result.get('reason', '同步失敗')}"
                )

        except Exception as error:
            summary[
                "failed_chapter_count"
            ] += 1
            summary["errors"].append(
                f"Module {chapter_id}：{error}"
            )

    return summary





def sync_single_chapter_cache_to_sqlite(
    document_name: str,
    document_id: str | int,
    source_chapter_id: str | int,
    chapter_title: str,
) -> dict:
    """
    將單一章節的詳細學習筆記快取寫回 SQLite。

    特性：
    - 不呼叫 AI
    - 不建立或修改 Notion 頁面
    - 不依賴 Notion 匯出狀態
    - 只有 SQLite 該章沒有 Quiz 與 Flash Cards 時才同步
    - 避免覆蓋既有 QuizAttempt、FlashcardReview 與 WeakPoint
    """

    normalized_source_chapter_id = str(
        source_chapter_id
    ).strip()

    normalized_chapter_title = str(
        chapter_title or
        f"Module {normalized_source_chapter_id}"
    ).strip()

    if not normalized_source_chapter_id:
        raise ValueError(
            "缺少 source_chapter_id，"
            "無法定位章節快取。"
        )

    resolved_document_id = _resolve_document_id(
        document_name=document_name,
        document_id=document_id,
    )

    if not resolved_document_id:
        raise ValueError(
            "找不到對應的 SQLite 文件 ID。"
        )

    existing_counts = (
        count_chapter_learning_items(
            document_id=resolved_document_id,
            source_chapter_id=(
                normalized_source_chapter_id
            ),
        )
    )

    existing_quiz_count = int(
        existing_counts.get(
            "quiz_count",
            0,
        )
        or 0
    )

    existing_flashcard_count = int(
        existing_counts.get(
            "flashcard_count",
            0,
        )
        or 0
    )

    if (
        existing_quiz_count > 0
        or existing_flashcard_count > 0
    ):
        return {
            "synced": False,
            "skipped": True,
            "reason": (
                "該章 SQLite 已有 Quiz 或 Flash Cards。"
                "請先在資料管理頁清除該章學習資料，"
                "再執行重新同步。"
            ),
            "document_id": resolved_document_id,
            "source_chapter_id": (
                normalized_source_chapter_id
            ),
            "chapter_title": (
                normalized_chapter_title
            ),
            "quiz_count": existing_quiz_count,
            "flashcard_count": (
                existing_flashcard_count
            ),
        }

    cache_chapter = {
        "chapter_id": (
            normalized_source_chapter_id
        ),
        "source_chapter_id": (
            normalized_source_chapter_id
        ),
        "chapter_order": (
            normalized_source_chapter_id
        ),
        "title": normalized_chapter_title,
        "chapter_title": (
            normalized_chapter_title
        ),
    }

    cached_data = load_chapter_cache(
        document_name=document_name,
        chapter=cache_chapter,
    )

    chapter_note = cached_data.get(
        "chapter_note"
    )

    if not cached_data.get(
        "note_cached"
    ):
        return {
            "synced": False,
            "skipped": False,
            "reason": (
                "找不到這個章節的詳細筆記快取。"
                "可能是舊版快取格式或快取檔案已不存在。"
            ),
            "document_id": resolved_document_id,
            "source_chapter_id": (
                normalized_source_chapter_id
            ),
            "chapter_title": (
                normalized_chapter_title
            ),
            "quiz_count": 0,
            "flashcard_count": 0,
        }

    if not cached_data.get(
        "note_cache_valid"
    ):
        return {
            "synced": False,
            "skipped": False,
            "reason": (
                "章節快取存在，但未通過目前版本的"
                " ChapterLearningNote 格式驗證。"
            ),
            "document_id": resolved_document_id,
            "source_chapter_id": (
                normalized_source_chapter_id
            ),
            "chapter_title": (
                normalized_chapter_title
            ),
            "quiz_count": 0,
            "flashcard_count": 0,
        }

    if chapter_note is None:
        return {
            "synced": False,
            "skipped": False,
            "reason": (
                "章節快取中沒有可讀取的詳細筆記內容。"
            ),
            "document_id": resolved_document_id,
            "source_chapter_id": (
                normalized_source_chapter_id
            ),
            "chapter_title": (
                normalized_chapter_title
            ),
            "quiz_count": 0,
            "flashcard_count": 0,
        }

    is_valid, reason = is_valid_chapter_note(
        chapter_note
    )

    if not is_valid:
        return {
            "synced": False,
            "skipped": False,
            "reason": (
                "章節詳細筆記快取無效："
                f"{reason}"
            ),
            "document_id": resolved_document_id,
            "source_chapter_id": (
                normalized_source_chapter_id
            ),
            "chapter_title": (
                normalized_chapter_title
            ),
            "quiz_count": 0,
            "flashcard_count": 0,
        }

    result = _sync_chapter_note_to_sqlite(
        document_id=resolved_document_id,
        chapter_id=(
            normalized_source_chapter_id
        ),
        chapter_note=chapter_note,
        force=False,
    )

    return {
        "synced": bool(
            result.get("synced")
        ),
        "skipped": bool(
            result.get("skipped")
        ),
        "reason": result.get(
            "reason",
            "",
        ),
        "document_id": resolved_document_id,
        "source_chapter_id": (
            normalized_source_chapter_id
        ),
        "chapter_title": (
            normalized_chapter_title
        ),
        "quiz_count": int(
            result.get(
                "quiz_count",
                0,
            )
            or 0
        ),
        "flashcard_count": int(
            result.get(
                "flashcard_count",
                0,
            )
            or 0
        ),
    }


def sync_document_learning_cache_to_sqlite(
    document_name: str,
    chapters: list[dict],
    document_id: str | int | None = None,
) -> dict:
    """
    將既有詳細學習筆記快取回填至 SQLite。

    這個流程：
    - 不建立或修改 Notion 頁面
    - 不呼叫 AI
    - 不依賴 Notion 匯出狀態
    - 只讀取有效的 ChapterLearningNote 快取
    - SQLite 已有 Quiz / Flash Cards 時會跳過，避免洗掉練習紀錄
    """

    resolved_document_id = _resolve_document_id(
        document_name=document_name,
        document_id=document_id,
    )

    summary = _sync_cached_notes_to_sqlite(
        document_name=document_name,
        document_id=resolved_document_id,
        chapters=chapters,
    )

    return {
        "document_name": document_name,
        "document_id": resolved_document_id,
        "synced_chapter_count": int(
            summary.get("synced_chapter_count", 0) or 0
        ),
        "skipped_chapter_count": int(
            summary.get("skipped_chapter_count", 0) or 0
        ),
        "failed_chapter_count": int(
            summary.get("failed_chapter_count", 0) or 0
        ),
        "synced_quiz_count": int(
            summary.get("synced_quiz_count", 0) or 0
        ),
        "synced_flashcard_count": int(
            summary.get("synced_flashcard_count", 0) or 0
        ),
        "errors": list(summary.get("errors", []) or []),
    }


def create_document_learning_notebook(
    document_name: str,
    chapters: list[dict],
    parsed_document: dict,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
    max_visual_pages: int = 3,
    resume: bool = True,
    document_id: str | int | None = None,
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

    resolved_document_id = _resolve_document_id(
        document_name=document_name,
        document_id=document_id,
    )

    sqlite_sync_summary = (
        _sync_cached_notes_to_sqlite(
            document_name=document_name,
            document_id=resolved_document_id,
            chapters=chapters,
        )
    )

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

        parent_blocks = _build_parent_page_blocks(
            document_name=document_name,
            chapter_count=chapter_count,
        )

        _append_blocks(
            notion=notion,
            page_id=parent_page_id,
            blocks=parent_blocks,
        )

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
            "sqlite_synced_chapter_count": sqlite_sync_summary.get(
                "synced_chapter_count",
                0,
            ),
            "sqlite_skipped_chapter_count": sqlite_sync_summary.get(
                "skipped_chapter_count",
                0,
            ),
            "sqlite_failed_chapter_count": sqlite_sync_summary.get(
                "failed_chapter_count",
                0,
            ),
            "sqlite_synced_quiz_count": sqlite_sync_summary.get(
                "synced_quiz_count",
                0,
            ),
            "sqlite_synced_flashcard_count": sqlite_sync_summary.get(
                "synced_flashcard_count",
                0,
            ),
            "sqlite_sync_errors": sqlite_sync_summary.get(
                "errors",
                [],
            ),
            "is_finished": True,
        }

    for index, chapter in enumerate(pending_chapters, start=1):
        chapter_id = str(chapter.get("chapter_id") or index)
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

            sync_result = _sync_chapter_note_to_sqlite(
                document_id=resolved_document_id,
                chapter_id=chapter_id,
                chapter_note=chapter_note,
                force=not note_used_cache,
            )

            if sync_result.get("synced"):
                sqlite_sync_summary[
                    "synced_chapter_count"
                ] += 1
                sqlite_sync_summary[
                    "synced_quiz_count"
                ] += int(
                    sync_result.get(
                        "quiz_count",
                        0,
                    )
                    or 0
                )
                sqlite_sync_summary[
                    "synced_flashcard_count"
                ] += int(
                    sync_result.get(
                        "flashcard_count",
                        0,
                    )
                    or 0
                )

            elif sync_result.get("skipped"):
                sqlite_sync_summary[
                    "skipped_chapter_count"
                ] += 1

            else:
                sqlite_sync_summary[
                    "failed_chapter_count"
                ] += 1
                sqlite_sync_summary.setdefault(
                    "errors",
                    [],
                ).append(
                    f"Module {chapter_id}："
                    f"{sync_result.get('reason', 'SQLite 同步失敗')}"
                )

            is_valid, reason = is_valid_chapter_note(chapter_note)

            if not is_valid:
                raise ValueError(
                    f"拒絕建立 Notion 子頁，詳細筆記無效：{reason}"
                )

            child_page_title = (
                f"Module {chapter_id}｜"
                f"{chapter_title}"
            )

            child_page = _create_page(
                notion=notion,
                title=child_page_title,
                parent_page_id=parent_page_id,
            )

            child_page_id = child_page["id"]
            child_page_url = child_page.get("url")

            (
                blocks,
                visual_upload_errors,
            ) = _build_chapter_note_blocks(
                chapter_note=chapter_note,
                visual_context=visual_context,
                chapter_id=chapter_id,
            )

            if visual_upload_errors:
                sqlite_sync_summary.setdefault(
                    "errors",
                    [],
                ).extend(
                    [
                        (
                            f"Module {chapter_id} "
                            f"圖片上傳：{message}"
                        )
                        for message
                        in visual_upload_errors
                    ]
                )

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
        "sqlite_synced_chapter_count": sqlite_sync_summary.get(
            "synced_chapter_count",
            0,
        ),
        "sqlite_skipped_chapter_count": sqlite_sync_summary.get(
            "skipped_chapter_count",
            0,
        ),
        "sqlite_failed_chapter_count": sqlite_sync_summary.get(
            "failed_chapter_count",
            0,
        ),
        "sqlite_synced_quiz_count": sqlite_sync_summary.get(
            "synced_quiz_count",
            0,
        ),
        "sqlite_synced_flashcard_count": sqlite_sync_summary.get(
            "synced_flashcard_count",
            0,
        ),
        "sqlite_sync_errors": sqlite_sync_summary.get(
            "errors",
            [],
        ),
        "is_finished": is_finished,
        "updated_at": datetime.utcnow().isoformat(),
    }