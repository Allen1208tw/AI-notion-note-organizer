from __future__ import annotations

import base64
from io import BytesIO

from src.config.settings import GEMINI_API_KEY, GEMINI_DETAIL_MODEL


def get_gemini_client():
    """Create a Gemini API client only when Gemini is actually used."""

    if not GEMINI_API_KEY:
        raise ValueError("找不到 Gemini API Key，請先到設定頁輸入 GEMINI_API_KEY。")

    try:
        from google import genai
    except ImportError as error:
        raise RuntimeError(
            "尚未安裝 Gemini SDK。請安裝 google-genai 後再使用 Gemini 模式。"
        ) from error

    return genai.Client(api_key=GEMINI_API_KEY)


def generate_gemini_text(
    *,
    prompt: str,
    system_instruction: str = "",
    model: str | None = None,
    temperature: float = 0.2,
) -> str:
    """Generate text with Gemini."""

    try:
        from google.genai import types
    except ImportError as error:
        raise RuntimeError(
            "尚未安裝 Gemini SDK。請安裝 google-genai 後再使用 Gemini 模式。"
        ) from error

    client = get_gemini_client()
    selected_model = str(model or GEMINI_DETAIL_MODEL or "gemini-3.5-flash")

    response = client.models.generate_content(
        model=selected_model,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction or None,
            temperature=temperature,
            response_mime_type="application/json",
        ),
    )

    return str(getattr(response, "text", "") or "")


def _image_from_data_url(data_url: str):
    try:
        from PIL import Image
    except ImportError as error:
        raise RuntimeError("Gemini 圖片分析需要 Pillow。") from error

    if "," not in str(data_url or ""):
        raise ValueError("圖片資料格式錯誤，缺少 data URL。")

    _, encoded = str(data_url).split(",", 1)
    image_bytes = base64.b64decode(encoded)
    return Image.open(BytesIO(image_bytes))


def generate_gemini_multimodal_text(
    *,
    prompt: str,
    image_data_urls: list[str],
    system_instruction: str = "",
    model: str | None = None,
    temperature: float = 0.2,
) -> str:
    """Generate text with Gemini from text plus local images."""

    try:
        from google.genai import types
    except ImportError as error:
        raise RuntimeError(
            "尚未安裝 Gemini SDK。請安裝 google-genai 後再使用 Gemini 模式。"
        ) from error

    client = get_gemini_client()
    selected_model = str(model or GEMINI_DETAIL_MODEL or "gemini-3.5-flash")
    contents = [prompt]
    contents.extend(_image_from_data_url(item) for item in image_data_urls)

    response = client.models.generate_content(
        model=selected_model,
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction or None,
            temperature=temperature,
            response_mime_type="application/json",
        ),
    )

    return str(getattr(response, "text", "") or "")


def test_gemini_connection() -> str:
    """Test whether Gemini API can respond."""

    try:
        text = generate_gemini_text(
            prompt='請只回覆 JSON：{"message":"Gemini API 連線成功"}',
            system_instruction="你只輸出 JSON，不輸出 Markdown。",
            temperature=0.0,
        )
    except Exception as error:
        raise RuntimeError(f"Gemini API 連線失敗：{error}") from error

    if "Gemini" not in text:
        return "Gemini API 已回應，但回覆格式與預期不同。"

    return "Gemini API 連線成功。"
