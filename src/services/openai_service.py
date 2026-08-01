from openai import OpenAI

from src.config.runtime_paths import ENV_FILE
from src.config.settings import OPENAI_MODEL


def _load_openai_api_key() -> str:
    """每次建立 client 時重新讀取 .env，避免設定頁更新後仍使用舊 key。"""

    try:
        from dotenv import dotenv_values

        value = str(
            dotenv_values(ENV_FILE).get("OPENAI_API_KEY")
            or ""
        ).strip()
    except Exception:
        value = ""

    if value:
        return value

    import os

    return str(os.getenv("OPENAI_API_KEY") or "").strip()


def get_openai_client() -> OpenAI:
    """建立 OpenAI API Client。"""

    api_key = _load_openai_api_key()

    if not api_key:
        raise ValueError("找不到 OpenAI API Key，請檢查 .env 設定。")

    return OpenAI(api_key=api_key)


def test_openai_connection() -> str:
    """測試 OpenAI API 是否可以正常連線。"""

    client = get_openai_client()

    try:
        response = client.responses.create(
            model=OPENAI_MODEL,
            input="請只回覆：OpenAI API 連線成功",
        )

        return response.output_text

    except Exception as error:
        raise RuntimeError(f"OpenAI API 連線失敗：{error}") from error
