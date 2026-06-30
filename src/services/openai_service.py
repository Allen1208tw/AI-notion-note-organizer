from openai import OpenAI

from src.config.settings import OPENAI_API_KEY, OPENAI_MODEL


def get_openai_client() -> OpenAI:
    """建立 OpenAI API Client。"""

    if not OPENAI_API_KEY:
        raise ValueError("找不到 OpenAI API Key，請檢查 .env 設定。")

    return OpenAI(api_key=OPENAI_API_KEY)


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