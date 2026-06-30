from datetime import datetime

from notion_client import Client

from src.config.settings import NOTION_API_KEY, NOTION_PARENT_PAGE_ID
from src.models.analysis_models import AnalysisResult
from src.validators.mermaid_validator import validate_mermaid


def get_notion_client() -> Client:
    """建立 Notion API 客戶端。"""

    if not NOTION_API_KEY:
        raise ValueError("找不到 NOTION_API_KEY，請檢查 .env 設定。")

    if not NOTION_PARENT_PAGE_ID:
        raise ValueError("找不到 NOTION_PARENT_PAGE_ID，請檢查 .env 設定。")

    return Client(auth=NOTION_API_KEY)


def text_content(content: str) -> list[dict]:
    """轉成 Notion rich_text 格式。"""

    return [
        {
            "type": "text",
            "text": {
                "content": content,
            },
        }
    ]


def heading_block(content: str, level: int = 2) -> dict:
    """建立 Notion 標題區塊。"""

    heading_type = f"heading_{level}"

    return {
        "object": "block",
        "type": heading_type,
        heading_type: {
            "rich_text": text_content(content),
        },
    }


def paragraph_block(content: str) -> dict:
    """建立 Notion 段落區塊。"""

    return {
        "object": "block",
        "type": "paragraph",
        "paragraph": {
            "rich_text": text_content(content),
        },
    }


def bullet_block(content: str) -> dict:
    """建立 Notion 項目符號區塊。"""

    return {
        "object": "block",
        "type": "bulleted_list_item",
        "bulleted_list_item": {
            "rich_text": text_content(content),
        },
    }


def toggle_block(title: str, child_content: str) -> dict:
    """建立可收合 Toggle 區塊。"""

    return {
        "object": "block",
        "type": "toggle",
        "toggle": {
            "rich_text": text_content(title),
            "children": [
                paragraph_block(child_content),
            ],
        },
    }


def code_block(content: str, language: str = "plain text") -> dict:
    """建立程式碼區塊。"""

    return {
        "object": "block",
        "type": "code",
        "code": {
            "rich_text": text_content(content),
            "language": language,
        },
    }


def build_notion_blocks(analysis_result: AnalysisResult) -> list[dict]:
    """將 AI 分析結果轉換成 Notion 區塊。"""

    blocks = []

    blocks.append(heading_block("文件摘要"))
    blocks.append(paragraph_block(analysis_result.summary))

    blocks.append(heading_block("重點整理"))

    if analysis_result.key_points:
        for point in analysis_result.key_points:
            blocks.append(bullet_block(point))
    else:
        blocks.append(paragraph_block("本次未產生重點整理。"))

    blocks.append(heading_block("Mermaid 圖表"))

    is_mermaid_valid, _ = validate_mermaid(analysis_result.mermaid)

    if is_mermaid_valid:
        blocks.append(code_block(analysis_result.mermaid))
    else:
        blocks.append(paragraph_block("本次未產生可用的 Mermaid 圖表。"))

    blocks.append(heading_block("Quiz"))

    if analysis_result.quiz:
        for index, item in enumerate(analysis_result.quiz, start=1):
            blocks.append(
                toggle_block(
                    title=f"第 {index} 題：{item.question}",
                    child_content=f"答案：{item.answer}",
                )
            )
    else:
        blocks.append(paragraph_block("本次未產生 Quiz。"))

    blocks.append(heading_block("Flash Cards"))

    if analysis_result.flashcards:
        for index, card in enumerate(analysis_result.flashcards, start=1):
            blocks.append(
                toggle_block(
                    title=f"Flash Card {index}：{card.front}",
                    child_content=f"背面：{card.back}",
                )
            )
    else:
        blocks.append(paragraph_block("本次未產生 Flash Cards。"))

    return blocks


def create_notion_page(
    document_name: str,
    analysis_result: AnalysisResult,
) -> str:
    """在指定 Notion 父頁面下建立整理完成的筆記頁面。"""

    client = get_notion_client()

    page_title = (
        f"{document_name}｜AI 整理筆記｜"
        f"{datetime.now().strftime('%Y-%m-%d %H:%M')}"
    )

    blocks = build_notion_blocks(analysis_result)

    response = client.pages.create(
        parent={
            "type": "page_id",
            "page_id": NOTION_PARENT_PAGE_ID,
        },
        properties={
            "title": {
                "title": text_content(page_title),
            },
        },
        children=blocks,
    )

    return response["url"]