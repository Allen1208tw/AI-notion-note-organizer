from pathlib import Path

import streamlit as st

from src.config.settings import OPENAI_MODEL, SUPPORTED_FILE_TYPES
from src.exporters.json_exporter import build_json
from src.exporters.markdown_builder import build_markdown
from src.parsers.docx_parser import parse_docx_file
from src.parsers.markdown_parser import parse_markdown_file
from src.parsers.pdf_parser import parse_pdf_file
from src.parsers.text_parser import parse_text_file
from src.processors.text_cleaner import clean_text
from src.processors.text_chunker import chunk_text
from src.services.analysis_service import analyze_chunk, analyze_document
from src.services.file_validator import validate_file
from src.services.notion_service import create_notion_page
from src.services.openai_service import test_openai_connection
from src.validators.mermaid_validator import validate_mermaid


st.set_page_config(
    page_title="AI Notion 筆記整理器",
    page_icon="📝",
    layout="wide",
)


def parse_uploaded_file(uploaded_file, extension: str) -> dict:
    """依照副檔名使用對應 Parser。"""

    parser_map = {
        ".txt": parse_text_file,
        ".md": parse_markdown_file,
        ".pdf": parse_pdf_file,
        ".docx": parse_docx_file,
    }

    parser = parser_map.get(extension)

    if parser is None:
        raise ValueError("不支援的檔案格式。")

    return parser(uploaded_file)


def clear_previous_result() -> None:
    """清除舊文件與分析結果。"""

    keys = [
        "current_file_name",
        "parsed_document",
        "cleaned_text",
        "chunks",
        "chunk_result",
        "final_result",
        "all_chunk_results",
    ]

    for key in keys:
        st.session_state.pop(key, None)


def show_chunk_result() -> None:
    """顯示單一 Chunk 分析結果。"""

    if "chunk_result" not in st.session_state:
        return

    result = st.session_state["chunk_result"]

    st.divider()
    st.subheader("🤖 第一段 AI 分析結果")

    st.subheader("📌 段落摘要")
    st.write(getattr(result, "chunk_summary", "AI 沒有回傳摘要。"))

    st.subheader("🧠 重點整理")

    key_points = getattr(result, "key_points", [])

    if key_points:
        for point in key_points:
            st.write(f"- {point}")
    else:
        st.info("這次 AI 沒有回傳重點整理。")

    st.subheader("📚 關鍵術語")

    terms = getattr(result, "terms", [])

    if terms:
        for term in terms:
            st.write(f"- {term}")
    else:
        st.info("這次 AI 沒有回傳關鍵術語。")

    st.subheader("❓ Quiz 題目素材")

    quiz_candidates = getattr(result, "quiz_candidates", [])

    if quiz_candidates:
        for item in quiz_candidates:
            st.write(f"Q：{item.question}")
            st.write(f"A：{item.answer}")
            st.divider()
    else:
        st.info("這次 AI 沒有回傳 Quiz 題目。")

    st.subheader("🗂️ Flash Card 素材")

    flashcards = getattr(result, "flashcard_candidates", [])

    if flashcards:
        for card in flashcards:
            st.write(f"正面：{card.front}")
            st.write(f"背面：{card.back}")
            st.divider()
    else:
        st.info("這次 AI 沒有回傳 Flash Card。")


def show_final_result(document_name: str) -> None:
    """顯示完整文件分析結果與下載按鈕。"""

    if "final_result" not in st.session_state:
        return

    final_result = st.session_state["final_result"]

    markdown_output = build_markdown(
        document_name=document_name,
        analysis_result=final_result,
    )

    json_output = build_json(
        document_name=document_name,
        analysis_result=final_result,
    )

    safe_name = Path(document_name).stem

    st.divider()
    st.subheader("📘 完整筆記整理結果")

    st.subheader("📝 文件摘要")
    st.write(final_result.summary)

    st.subheader("🧠 重點整理")

    if final_result.key_points:
        for point in final_result.key_points:
            st.write(f"- {point}")
    else:
        st.info("這次沒有產生重點整理。")

    st.subheader("🗺️ Mermaid 圖表")

    is_mermaid_valid, mermaid_error = validate_mermaid(
        final_result.mermaid
    )

    if is_mermaid_valid:
        st.code(
            final_result.mermaid,
            language="text",
        )
    else:
        st.warning(f"Mermaid 圖表無法使用：{mermaid_error}")

    st.subheader("❓ Quiz")

    if final_result.quiz:
        for index, item in enumerate(final_result.quiz, start=1):
            with st.expander(f"第 {index} 題"):
                st.write(f"Q：{item.question}")
                st.write(f"A：{item.answer}")
    else:
        st.info("這次沒有產生 Quiz。")

    st.subheader("🗂️ Flash Cards")

    if final_result.flashcards:
        for index, card in enumerate(final_result.flashcards, start=1):
            with st.expander(f"Flash Card {index}"):
                st.write(f"正面：{card.front}")
                st.write(f"背面：{card.back}")
    else:
        st.info("這次沒有產生 Flash Cards。")

    st.divider()
    st.subheader("📤 匯出結果")

    if st.button("建立 Notion 筆記頁面", type="primary"):
        with st.spinner("正在建立 Notion 筆記頁面..."):
            try:
                notion_page_url = create_notion_page(
                    document_name=document_name,
                    analysis_result=final_result,
                )

                st.success("Notion 筆記頁面建立完成。")

                st.link_button(
                    "開啟 Notion 筆記頁面",
                    notion_page_url,
                )

            except Exception as error:
                st.error(f"建立 Notion 頁面失敗：{error}")

    export_col1, export_col2 = st.columns(2)

    export_col1.download_button(
        label="下載 Notion Markdown",
        data=markdown_output,
        file_name=f"{safe_name}_notion_notes.md",
        mime="text/markdown",
    )

    export_col2.download_button(
        label="下載 JSON 資料",
        data=json_output,
        file_name=f"{safe_name}_analysis.json",
        mime="application/json",
    )

    with st.expander("預覽 Notion Markdown"):
        st.code(
            markdown_output,
            language="markdown",
        )


st.title("📝 AI Notion 筆記整理器")
st.caption("上傳文件，自動整理成適合貼到 Notion 的結構化筆記。")

if st.button("測試 AI 連線"):
    with st.spinner("正在測試 OpenAI API 連線..."):
        try:
            connection_result = test_openai_connection()
            st.success(connection_result)

        except Exception as error:
            st.error(f"AI 連線失敗：{error}")

st.divider()
st.subheader("📤 上傳文件")

uploaded_file = st.file_uploader(
    "請選擇檔案",
    type=["pdf", "docx", "txt", "md"],
    help=f"支援格式：{', '.join(SUPPORTED_FILE_TYPES)}",
)

if uploaded_file is None:
    st.info("請先上傳 PDF、DOCX、TXT 或 Markdown 檔案。")

else:
    if (
        "current_file_name" in st.session_state
        and st.session_state["current_file_name"] != uploaded_file.name
    ):
        clear_previous_result()

    file_size_mb = uploaded_file.size / (1024 * 1024)

    col1, col2, col3 = st.columns(3)

    col1.metric("檔案名稱", uploaded_file.name)
    col2.metric("檔案大小", f"{file_size_mb:.2f} MB")
    col3.metric("AI 模型", OPENAI_MODEL)

    is_valid, error_message = validate_file(uploaded_file)

    if not is_valid:
        st.error(error_message)

    else:
        st.success("檔案驗證通過。")

        if st.button("開始分析", type="primary"):
            try:
                extension = Path(uploaded_file.name).suffix.lower()

                parsed_document = parse_uploaded_file(
                    uploaded_file,
                    extension,
                )

                raw_text = parsed_document["raw_text"]

                if not raw_text.strip():
                    st.warning("這份文件沒有可讀取的文字內容。")
                    st.stop()

                cleaned_text = clean_text(raw_text)
                chunks = chunk_text(cleaned_text)

                if not chunks:
                    st.warning("文件清理後沒有可供分析的內容。")
                    st.stop()

                st.session_state["current_file_name"] = uploaded_file.name
                st.session_state["parsed_document"] = parsed_document
                st.session_state["cleaned_text"] = cleaned_text
                st.session_state["chunks"] = chunks

                st.session_state.pop("chunk_result", None)
                st.session_state.pop("final_result", None)
                st.session_state.pop("all_chunk_results", None)

                st.success("檔案解析、文字清理與分段完成。")

            except Exception as error:
                st.error(f"文件處理失敗：{error}")

if "parsed_document" in st.session_state:
    parsed_document = st.session_state["parsed_document"]
    metadata = parsed_document["metadata"]
    cleaned_text = st.session_state["cleaned_text"]
    chunks = st.session_state["chunks"]

    st.divider()
    st.subheader("📄 文件解析結果")

    preview_col1, preview_col2, preview_col3 = st.columns(3)

    preview_col1.metric(
        "文字字數",
        metadata["character_count"],
    )

    preview_col2.metric(
        "段落數量",
        metadata["paragraph_count"],
    )

    preview_col3.metric(
        "檔案格式",
        metadata["file_extension"],
    )

    st.text_area(
        "清理後文字預覽",
        value=cleaned_text,
        height=300,
    )

    st.subheader("✂️ 文字分段預覽")
    st.metric("分段總數", len(chunks))

    for chunk in chunks:
        title = (
            f"第 {chunk['chunk_id']} 段｜"
            f"{chunk['character_count']} 字元"
        )

        with st.expander(title):
            st.text(chunk["content"])

    st.divider()
    st.subheader("📚 完整文件 AI 分析")

    if st.button("分析整份文件", type="primary"):
        with st.spinner("AI 正在分析所有內容並整合筆記..."):
            try:
                final_result, chunk_results = analyze_document(chunks)

                st.session_state["final_result"] = final_result
                st.session_state["all_chunk_results"] = chunk_results

                st.success("完整文件分析完成。")

            except Exception as error:
                st.error(f"完整文件分析失敗：{error}")

    st.divider()
    st.subheader("🤖 單段分析測試")

    if st.button("分析第一段內容"):
        first_chunk = chunks[0]

        with st.spinner("AI 正在分析第一段內容..."):
            try:
                chunk_result = analyze_chunk(
                    chunk_content=first_chunk["content"],
                    chunk_id=first_chunk["chunk_id"],
                )

                st.session_state["chunk_result"] = chunk_result

                st.success("第一段 AI 分析完成。")

            except Exception as error:
                st.error(f"AI 分析失敗：{error}")

show_chunk_result()

if uploaded_file is not None:
    show_final_result(uploaded_file.name)