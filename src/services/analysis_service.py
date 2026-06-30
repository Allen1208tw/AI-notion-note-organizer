import json

from src.config.settings import OPENAI_CHUNK_MODEL, OPENAI_MERGE_MODEL
from src.models.analysis_models import AnalysisResult, ChunkAnalysisResult
from src.prompts.chunk_prompt import build_chunk_prompt
from src.prompts.merge_prompt import build_merge_prompt
from src.prompts.mermaid_quality_prompt import build_mermaid_quality_prompt
from src.prompts.mermaid_repair_prompt import build_mermaid_repair_prompt
from src.prompts.summary_quality_prompt import build_summary_quality_prompt
from src.prompts.system_prompt import SYSTEM_PROMPT
from src.services.openai_service import get_openai_client
from src.validators.mermaid_validator import validate_mermaid


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
        raise ValueError("AI 回覆中找不到合法 JSON。")

    return json.loads(cleaned_text[start_index:end_index + 1])


def _extract_mermaid(raw_text: str) -> str:
    """清理 Mermaid 回覆中的 Code Fence 與多餘文字。"""

    cleaned_text = raw_text.strip()
    cleaned_text = cleaned_text.replace("```mermaid", "")
    cleaned_text = cleaned_text.replace("```", "")

    lines = cleaned_text.splitlines()
    start_index = None

    for index, line in enumerate(lines):
        line_text = line.strip()

        if (
            line_text.startswith("flowchart TD")
            or line_text.startswith("flowchart LR")
            or line_text.startswith("mindmap")
            or line_text.startswith("sequenceDiagram")
        ):
            start_index = index
            break

    if start_index is None:
        return cleaned_text.strip()

    return "\n".join(lines[start_index:]).strip()


def _request_json(model: str, prompt: str) -> dict:
    """向 OpenAI 請求 JSON 格式結果。"""

    client = get_openai_client()

    response = client.responses.create(
        model=model,
        instructions=SYSTEM_PROMPT,
        input=prompt,
    )

    raw_text = response.output_text.strip()

    try:
        return _extract_json(raw_text)

    except json.JSONDecodeError as error:
        raise RuntimeError(
            "AI 回傳的 JSON 格式錯誤，請重新分析一次。"
        ) from error


def _request_mermaid(prompt: str) -> str:
    """向 OpenAI 請求 Mermaid 原始碼。"""

    client = get_openai_client()

    response = client.responses.create(
        model=OPENAI_MERGE_MODEL,
        instructions=SYSTEM_PROMPT,
        input=prompt,
    )

    return _extract_mermaid(response.output_text)


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
) -> list[ChunkAnalysisResult]:
    """逐段分析完整文件。"""

    chunk_results = []

    for chunk in chunks:
        chunk_result = analyze_chunk(
            chunk_content=chunk["content"],
            chunk_id=chunk["chunk_id"],
        )

        chunk_results.append(chunk_result)

    return chunk_results


def evaluate_summary_quality(
    document_summary: str,
    chunk_results: list[ChunkAnalysisResult],
) -> dict:
    """檢查摘要是否完整涵蓋重要資訊。"""

    chunk_data = [
        result.model_dump()
        for result in chunk_results
    ]

    quality_prompt = build_summary_quality_prompt(
        document_summary=document_summary,
        chunk_results=chunk_data,
    )

    return _request_json(
        model=OPENAI_CHUNK_MODEL,
        prompt=quality_prompt,
    )


def repair_summary(
    analysis_result: AnalysisResult,
    chunk_results: list[ChunkAnalysisResult],
    missing_topics: list[str],
) -> AnalysisResult:
    """依照缺漏主題，重新整合完整摘要。"""

    chunk_data = [
        result.model_dump()
        for result in chunk_results
    ]

    missing_topics_text = "、".join(missing_topics)

    prompt = f"""
請根據以下各段分析結果，重新撰寫一份完整文件摘要。

你必須只輸出合法 JSON，不可輸出其他文字。

原本摘要：
{analysis_result.summary}

缺漏主題：
{missing_topics_text}

各段分析結果：
{chunk_data}

請依照以下格式輸出：

{{
  "summary": "完整且具覆蓋性的文件摘要"
}}

規則：
1. 使用繁體中文。
2. 摘要需保留原本重要資訊。
3. 必須補上缺漏主題。
4. 不可只整理前半段內容。
5. 避免使用「內容不足」、「後半段截斷」等文字，除非原始資料真的中斷。
6. 摘要建議 250 至 500 個中文字；文件較長時可以更長。
"""

    repaired_data = _request_json(
        model=OPENAI_MERGE_MODEL,
        prompt=prompt,
    )

    repaired_summary = repaired_data.get("summary", "").strip()

    if repaired_summary:
        analysis_result.summary = repaired_summary

    return analysis_result


def repair_summary_if_needed(
    analysis_result: AnalysisResult,
    chunk_results: list[ChunkAnalysisResult],
) -> AnalysisResult:
    """摘要缺漏重要內容時，自動補寫一次。"""

    quality_result = evaluate_summary_quality(
        document_summary=analysis_result.summary,
        chunk_results=chunk_results,
    )

    should_repair = quality_result.get("should_repair", False)
    missing_topics = quality_result.get("missing_topics", [])

    if should_repair and missing_topics:
        return repair_summary(
            analysis_result=analysis_result,
            chunk_results=chunk_results,
            missing_topics=missing_topics,
        )

    return analysis_result


def evaluate_mermaid_quality(
    document_summary: str,
    mermaid: str,
) -> dict:
    """評估 Mermaid 是否聚焦文件核心主題。"""

    quality_prompt = build_mermaid_quality_prompt(
        document_summary=document_summary,
        mermaid=mermaid,
    )

    return _request_json(
        model=OPENAI_CHUNK_MODEL,
        prompt=quality_prompt,
    )


def repair_mermaid(
    document_summary: str,
    current_mermaid: str,
    error_reason: str,
) -> str:
    """請 AI 修正 Mermaid。"""

    repair_prompt = build_mermaid_repair_prompt(
        document_summary=document_summary,
        current_mermaid=current_mermaid,
        error_reason=error_reason,
    )

    return _request_mermaid(repair_prompt)


def repair_mermaid_if_needed(
    analysis_result: AnalysisResult,
) -> AnalysisResult:
    """格式或語意不合格時，自動修正 Mermaid 一次。"""

    is_valid, error_reason = validate_mermaid(
        analysis_result.mermaid
    )

    if not is_valid:
        repaired_mermaid = repair_mermaid(
            document_summary=analysis_result.summary,
            current_mermaid=analysis_result.mermaid,
            error_reason=error_reason,
        )

        repaired_is_valid, _ = validate_mermaid(repaired_mermaid)

        if repaired_is_valid:
            analysis_result.mermaid = repaired_mermaid

        return analysis_result

    quality_result = evaluate_mermaid_quality(
        document_summary=analysis_result.summary,
        mermaid=analysis_result.mermaid,
    )

    should_repair = quality_result.get("should_repair", False)

    quality_reason = quality_result.get(
        "reason",
        "Mermaid 圖表未聚焦文件核心主題。",
    )

    if should_repair:
        repaired_mermaid = repair_mermaid(
            document_summary=analysis_result.summary,
            current_mermaid=analysis_result.mermaid,
            error_reason=quality_reason,
        )

        repaired_is_valid, _ = validate_mermaid(repaired_mermaid)

        if repaired_is_valid:
            analysis_result.mermaid = repaired_mermaid

    return analysis_result


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
) -> tuple[AnalysisResult, list[ChunkAnalysisResult]]:
    """完整分析文件：逐段分析後，再整合成最終筆記。"""

    chunk_results = analyze_all_chunks(chunks)

    final_result = merge_chunk_results(chunk_results)

    return final_result, chunk_results