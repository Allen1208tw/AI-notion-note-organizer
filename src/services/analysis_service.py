import json
from collections.abc import Callable

from src.config.settings import OPENAI_CHUNK_MODEL, OPENAI_MERGE_MODEL
from src.models.analysis_models import AnalysisResult, ChunkAnalysisResult
from src.prompts.chunk_prompt import build_chunk_prompt
from src.prompts.merge_prompt import build_merge_prompt
from src.prompts.system_prompt import SYSTEM_PROMPT
from src.services.openai_service import get_openai_client


def _extract_json(raw_text: str) -> dict:
    """從 AI 回覆中擷取合法 JSON。"""

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


def _request_json(model: str, prompt: str) -> dict:
    """向 OpenAI 請求 JSON；失敗時自動重試一次。"""

    client = get_openai_client()

    response = client.responses.create(
        model=model,
        instructions=SYSTEM_PROMPT,
        input=prompt,
    )

    raw_text = response.output_text.strip()

    try:
        return _extract_json(raw_text)

    except (json.JSONDecodeError, ValueError):
        retry_prompt = f"""
上一份回覆不是合法 JSON，請重新完成同一個任務。

請只輸出完整、合法的 JSON。
不可使用 Markdown Code Fence。
不可加入任何說明文字。
不可省略 JSON 的結尾大括號。

原本任務：
{prompt}
"""

        retry_response = client.responses.create(
            model=model,
            instructions=SYSTEM_PROMPT,
            input=retry_prompt,
        )

        retry_raw_text = retry_response.output_text.strip()

        try:
            return _extract_json(retry_raw_text)

        except (json.JSONDecodeError, ValueError) as error:
            raise RuntimeError(
                "AI 連續兩次回傳無法解析的 JSON。"
                "請縮短文件內容後重試，或重新分析一次。"
            ) from error


def analyze_chunk(
    chunk_content: str,
    chunk_id: int,
) -> ChunkAnalysisResult:
    """分析單一文字分段。"""

    prompt = build_chunk_prompt(
        chunk_content=chunk_content,
        chunk_id=chunk_id,
    )

    parsed_data = _request_json(
        model=OPENAI_CHUNK_MODEL,
        prompt=prompt,
    )

    return ChunkAnalysisResult.model_validate(parsed_data)


def analyze_all_chunks(
    chunks: list[dict],
    progress_callback: Callable[[int, int, str], None] | None = None,
    cancellation_check: Callable[[], None] | None = None,
) -> list[ChunkAnalysisResult]:
    """逐段分析完整文件。"""

    chunk_results = []

    total = len(chunks)

    for index, chunk in enumerate(chunks, start=1):
        if cancellation_check is not None:
            cancellation_check()

        chunk_result = analyze_chunk(
            chunk_content=chunk["content"],
            chunk_id=chunk["chunk_id"],
        )

        chunk_results.append(chunk_result)

        if progress_callback is not None:
            progress_callback(
                index,
                total + 1,
                f"完成第 {index} / {total} 個文字分段",
            )

    return chunk_results


def merge_chunk_results(
    chunk_results: list[ChunkAnalysisResult],
) -> AnalysisResult:
    """將所有 Chunk 分析結果整合成完整筆記。"""

    result_data = [
        result.model_dump()
        for result in chunk_results
    ]

    prompt = build_merge_prompt(result_data)

    parsed_data = _request_json(
        model=OPENAI_MERGE_MODEL,
        prompt=prompt,
    )

    return AnalysisResult.model_validate(parsed_data)


def analyze_document(
    chunks: list[dict],
    progress_callback: Callable[[int, int, str], None] | None = None,
    cancellation_check: Callable[[], None] | None = None,
) -> tuple[AnalysisResult, list[ChunkAnalysisResult]]:
    """完整分析文件：逐段分析後，再整合成最終筆記。"""

    total = len(chunks)
    chunk_results = analyze_all_chunks(
        chunks,
        progress_callback=progress_callback,
        cancellation_check=cancellation_check,
    )

    if cancellation_check is not None:
        cancellation_check()

    if progress_callback is not None:
        progress_callback(total, total + 1, "正在整合整份文件分析")

    final_result = merge_chunk_results(chunk_results)

    if progress_callback is not None:
        progress_callback(total + 1, total + 1, "整份文件分析完成")

    return final_result, chunk_results
