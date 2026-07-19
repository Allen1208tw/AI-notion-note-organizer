import json

from src.config.settings import AI_PROVIDER, GEMINI_DETAIL_MODEL, OPENAI_MERGE_MODEL
from src.models.chapter_models import ChapterLearningNote
from src.prompts.chapter_prompt import build_chapter_prompt
from src.prompts.system_prompt import SYSTEM_PROMPT
from src.services.gemini_service import generate_gemini_text
from src.services.openai_service import get_openai_client


def _extract_json(raw_text: str) -> dict:
    """從 AI 回覆中擷取 JSON。"""

    cleaned_text = raw_text.strip()

    if cleaned_text.startswith("```"):
        cleaned_text = cleaned_text.replace("```json", "", 1)
        cleaned_text = cleaned_text.replace("```", "", 1)
        cleaned_text = cleaned_text.strip()

    start_index = cleaned_text.find("{")
    end_index = cleaned_text.rfind("}")

    if start_index == -1 or end_index == -1:
        raise ValueError("AI 回覆中找不到完整 JSON。")

    json_text = cleaned_text[start_index:end_index + 1]

    return json.loads(json_text)


def _request_openai_chapter_note(prompt: str) -> str:
    client = get_openai_client()
    response = client.responses.create(
        model=OPENAI_MERGE_MODEL,
        instructions=SYSTEM_PROMPT,
        input=prompt,
    )
    return response.output_text


def _request_gemini_chapter_note(prompt: str) -> str:
    return generate_gemini_text(
        model=GEMINI_DETAIL_MODEL,
        system_instruction=SYSTEM_PROMPT,
        prompt=prompt,
        temperature=0.2,
    )


def _request_chapter_note(prompt: str) -> dict:
    """呼叫 OpenAI 產生章節詳細學習筆記。"""

    provider = str(AI_PROVIDER or "openai").strip().lower()
    if provider == "gemini":
        raw_text = _request_gemini_chapter_note(prompt)
    else:
        raw_text = _request_openai_chapter_note(prompt)

    try:
        return _extract_json(raw_text)

    except (json.JSONDecodeError, ValueError):
        retry_prompt = f"""
上一份回覆不是合法 JSON，請重新完成相同任務。

請務必遵守：
1. 只能輸出完整、合法 JSON。
2. 不可使用 Markdown Code Fence。
3. 不可加入前言、解釋、註解或其他文字。
4. 不可遺漏 JSON 的結尾大括號。
5. 所有欄位都必須符合原本提供的 JSON Schema。

原本任務：
{prompt}
"""

        if provider == "gemini":
            retry_raw_text = _request_gemini_chapter_note(retry_prompt)
        else:
            retry_raw_text = _request_openai_chapter_note(retry_prompt)

        try:
            return _extract_json(retry_raw_text)

        except (json.JSONDecodeError, ValueError) as error:
            raise RuntimeError(
                "AI 連續兩次回傳無法解析的章節學習筆記 JSON。"
            ) from error


def analyze_chapter(
    chapter: dict,
    visual_context: list[dict] | None = None,
) -> ChapterLearningNote:
    """
    分析單一主章節並產生詳細學習筆記。

    chapter 格式來自 detect_chapters()：
    {
        "title": "...",
        "content": "...",
        "subsections": [...]
    }

    visual_context 格式：
    [
        {
            "page_number": 10,
            "description": "圖片或畫面分析結果"
        }
    ]
    """

    chapter_title = chapter.get("title", "未命名章節")
    chapter_content = chapter.get("content", "").strip()
    subsections = chapter.get("subsections", [])

    if not chapter_content:
        raise ValueError("章節內容為空，無法產生學習筆記。")

    prompt = build_chapter_prompt(
        chapter_title=chapter_title,
        chapter_content=chapter_content,
        subsections=subsections,
        visual_context=visual_context,
    )

    result_data = _request_chapter_note(prompt)

    return ChapterLearningNote.model_validate(result_data)
