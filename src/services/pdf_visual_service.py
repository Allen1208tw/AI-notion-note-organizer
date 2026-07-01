from src.config.settings import OPENAI_MERGE_MODEL
from src.processors.pdf_visual_extractor import (
    render_pdf_pages_to_base64,
    select_representative_pages,
)
from src.services.openai_service import get_openai_client


def get_chapter_page_range(
    chapter: dict,
    page_texts: list[dict],
) -> tuple[int, int]:
    """
    根據主章節的字元範圍，找出對應的 PDF 頁碼範圍。
    """

    if not page_texts:
        raise ValueError("沒有 PDF 頁面文字資料。")

    chapter_start = chapter.get("start_index", 0)
    chapter_end = chapter.get("end_index", 0)

    matched_pages = []

    for page in page_texts:
        page_start = page["start_index"]
        page_end = page["end_index"]

        has_overlap = (
            chapter_start < page_end
            and chapter_end > page_start
        )

        if has_overlap:
            matched_pages.append(page["page_number"])

    if not matched_pages:
        return (
            page_texts[0]["page_number"],
            page_texts[-1]["page_number"],
        )

    return min(matched_pages), max(matched_pages)


def _build_visual_prompt(
    chapter_title: str,
    page_numbers: list[int],
) -> str:
    """建立 PDF 頁面視覺分析指令。"""

    page_text = "、".join(
        str(page_number)
        for page_number in page_numbers
    )

    return f"""
你是一位協助整理程式設計教材的視覺分析助教。

請分析以下 PDF 頁面圖片，判斷圖片中是否包含有助於學習的內容。

目前章節：
{chapter_title}

分析頁碼：
第 {page_text} 頁

請只整理圖片中真正看得到的資訊，不可捏造。

優先辨識：
1. 程式碼截圖
2. IDE 或 VS Code 操作畫面
3. 網頁呈現結果
4. 流程圖、架構圖、示意圖
5. 表格
6. 表單畫面
7. CSS 排版、樣式或版面效果

若頁面只是封面、Logo、裝飾圖片、沒有補充教學價值，
請直接忽略該頁。

請依照以下格式輸出純文字：

[PAGE:頁碼]
TYPE: code_screenshot / ui_screenshot / diagram / table / workflow / illustration
TITLE: 簡短標題
DESCRIPTION: 圖片內容與用途
LEARNING_POINTS:
- 重點一
- 重點二
RELATED_SUBSECTION: 可對應的子章節名稱，無法判斷就留空
"""


def _parse_visual_response(raw_text: str) -> list[dict]:
    """
    將 AI 回傳的視覺分析文字轉為結構化資料。
    """

    results = []
    current_item = None
    collecting_points = False

    for raw_line in raw_text.splitlines():
        line = raw_line.strip()

        if not line:
            continue

        if line.startswith("[PAGE:") and line.endswith("]"):
            if current_item:
                results.append(current_item)

            page_text = line.replace("[PAGE:", "").replace("]", "").strip()

            try:
                page_number = int(page_text)
            except ValueError:
                page_number = 0

            current_item = {
                "page_number": page_number,
                "image_type": "illustration",
                "title": "",
                "description": "",
                "learning_points": [],
                "related_subsection": "",
            }

            collecting_points = False
            continue

        if current_item is None:
            continue

        if line.startswith("TYPE:"):
            current_item["image_type"] = (
                line.replace("TYPE:", "", 1).strip()
            )
            collecting_points = False
            continue

        if line.startswith("TITLE:"):
            current_item["title"] = (
                line.replace("TITLE:", "", 1).strip()
            )
            collecting_points = False
            continue

        if line.startswith("DESCRIPTION:"):
            current_item["description"] = (
                line.replace("DESCRIPTION:", "", 1).strip()
            )
            collecting_points = False
            continue

        if line.startswith("LEARNING_POINTS:"):
            collecting_points = True
            continue

        if line.startswith("RELATED_SUBSECTION:"):
            current_item["related_subsection"] = (
                line.replace(
                    "RELATED_SUBSECTION:",
                    "",
                    1,
                ).strip()
            )
            collecting_points = False
            continue

        if collecting_points and line.startswith("-"):
            point = line.lstrip("-").strip()

            if point:
                current_item["learning_points"].append(point)

    if current_item:
        results.append(current_item)

    valid_results = []

    for item in results:
        has_meaningful_content = (
            item["title"]
            or item["description"]
            or item["learning_points"]
        )

        if has_meaningful_content:
            valid_results.append(item)

    return valid_results


def _attach_page_images(
    visual_context: list[dict],
    rendered_pages: list[dict],
) -> list[dict]:
    """
    將 PDF 頁面圖片 Data URL 對應回視覺分析結果。
    """

    image_map = {
        page["page_number"]: page["image_data_url"]
        for page in rendered_pages
    }

    for item in visual_context:
        page_number = item.get("page_number", 0)

        if page_number in image_map:
            item["image_data_url"] = image_map[page_number]

    return visual_context


def analyze_chapter_visuals(
    chapter: dict,
    pdf_bytes: bytes,
    page_texts: list[dict],
    max_pages: int = 3,
) -> list[dict]:
    """
    分析單一主章節對應的 PDF 頁面視覺內容。

    回傳資料包含：
    - page_number
    - image_type
    - title
    - description
    - learning_points
    - related_subsection
    - image_data_url
    """

    if not pdf_bytes or not page_texts:
        return []

    start_page, end_page = get_chapter_page_range(
        chapter=chapter,
        page_texts=page_texts,
    )

    selected_pages = select_representative_pages(
        start_page=start_page,
        end_page=end_page,
        max_pages=max_pages,
    )

    rendered_pages = render_pdf_pages_to_base64(
        pdf_bytes=pdf_bytes,
        page_numbers=selected_pages,
        zoom=1.4,
        max_pages=max_pages,
    )

    content = [
        {
            "type": "input_text",
            "text": _build_visual_prompt(
                chapter_title=chapter.get(
                    "title",
                    "未命名章節",
                ),
                page_numbers=selected_pages,
            ),
        }
    ]

    for rendered_page in rendered_pages:
        content.append(
            {
                "type": "input_image",
                "image_url": rendered_page["image_data_url"],
            }
        )

    client = get_openai_client()

    response = client.responses.create(
        model=OPENAI_MERGE_MODEL,
        input=[
            {
                "role": "user",
                "content": content,
            }
        ],
    )

    raw_text = response.output_text.strip()

    if not raw_text:
        return []

    visual_context = _parse_visual_response(raw_text)

    return _attach_page_images(
        visual_context=visual_context,
        rendered_pages=rendered_pages,
    )