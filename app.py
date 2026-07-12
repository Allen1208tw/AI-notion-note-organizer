from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from src.config.settings import OPENAI_MODEL, SUPPORTED_FILE_TYPES
from src.exporters.json_exporter import build_json
from src.exporters.markdown_builder import build_markdown
from src.parsers.docx_parser import parse_docx_file
from src.parsers.markdown_parser import parse_markdown_file
from src.parsers.pdf_parser import parse_pdf_file
from src.parsers.text_parser import parse_text_file
from src.processors.chapter_detector import detect_chapters
from src.processors.text_cleaner import clean_text
from src.processors.text_chunker import chunk_text
from src.services.analysis_service import analyze_chunk, analyze_document
from src.services.chapter_notion_service import (
    create_document_learning_notebook,
)
from src.services.chapter_service import analyze_chapter
from src.services.export_estimate_service import (
    estimate_document_export,
)
from src.services.file_validator import validate_file
from src.services.learning_database_service import (
    count_chapter_learning_items,
    count_document_learning_items,
    create_file_hash,
    create_or_update_document,
    mark_document_exporting,
    save_chapter_learning_items,
    update_document_export_result,
)
from src.services.notion_service import create_notion_page
from src.services.openai_service import test_openai_connection
from src.services.pdf_visual_service import analyze_chapter_visuals
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
    """清除前一份文件的畫面與暫存分析資料。"""

    keys = [
        "current_file_name",
        "current_document_id",
        "parsed_document",
        "cleaned_text",
        "chapters",
        "chunks",
        "chunk_result",
        "final_result",
        "all_chunk_results",
        "notion_page_url",
        "chapter_notes",
        "selected_chapter_note_id",
        "scroll_to_chapter_note",
        "chapter_visual_contexts",
        "document_notion_result",
    ]

    for key in keys:
        st.session_state.pop(key, None)


def show_callout(callout) -> None:
    """依照 Callout 類型顯示不同樣式。"""

    content = f"**{callout.icon} {callout.title}**\n\n{callout.content}"

    if callout.tone == "warning":
        st.warning(content)
    elif callout.tone == "success":
        st.success(content)
    else:
        st.info(content)


def show_comparison_table(table) -> None:
    """顯示 AI 回傳的比較表格。"""

    if not table.headers or not table.rows:
        return

    formatted_rows = []

    for row in table.rows:
        row_data = {}

        for index, header in enumerate(table.headers):
            row_data[header] = row[index] if index < len(row) else ""

        formatted_rows.append(row_data)

    st.markdown(f"#### 📊 {table.title}")
    st.table(formatted_rows)

    if table.note:
        st.caption(f"補充：{table.note}")


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


def show_chapter_learning_note(chapter_note) -> None:
    """顯示單一 Module 的詳細學習筆記。"""

    st.divider()
    st.header(f"📘 詳細學習筆記｜{chapter_note.chapter_title}")

    if chapter_note.callout_notes:
        st.subheader("✨ 重點標註")

        for callout in chapter_note.callout_notes:
            show_callout(callout)

    st.subheader("🎯 學習目標")

    if chapter_note.learning_objectives:
        for objective in chapter_note.learning_objectives:
            st.write(f"- {objective}")
    else:
        st.info("這次沒有產生學習目標。")

    st.subheader("📝 章節摘要")
    st.write(chapter_note.chapter_summary)

    st.subheader("🧠 白話講解")
    st.write(chapter_note.plain_explanation)

    st.subheader("⭐ 核心重點")

    if chapter_note.key_points:
        for point in chapter_note.key_points:
            st.write(f"- {point}")
    else:
        st.info("這次沒有產生核心重點。")

    st.subheader("📚 重要術語")

    if chapter_note.important_terms:
        for term in chapter_note.important_terms:
            st.write(f"- {term}")
    else:
        st.info("這次沒有產生重要術語。")

    st.subheader("📌 語法規則與注意事項")

    if chapter_note.syntax_rules:
        for rule in chapter_note.syntax_rules:
            st.write(f"- {rule}")
    else:
        st.info("這次沒有產生語法規則。")

    if chapter_note.comparison_tables:
        st.subheader("📊 重點比較表")

        for table in chapter_note.comparison_tables:
            show_comparison_table(table)

    st.subheader("💻 程式碼範例")

    if chapter_note.code_examples:
        for index, example in enumerate(
            chapter_note.code_examples,
            start=1,
        ):
            with st.expander(f"範例 {index}｜{example.title}"):
                st.code(
                    example.code,
                    language=example.language,
                )
                st.write(example.explanation)
    else:
        st.info("這個章節沒有產生程式碼範例。")

    st.subheader("⚠️ 常見錯誤與混淆")

    if chapter_note.common_mistakes:
        for index, mistake in enumerate(
            chapter_note.common_mistakes,
            start=1,
        ):
            with st.expander(f"常見錯誤 {index}"):
                st.write(f"容易出錯：{mistake.mistake}")
                st.write(f"正確觀念：{mistake.correction}")
    else:
        st.info("這次沒有產生常見錯誤提醒。")

    st.subheader("🧩 子章節整理")

    if chapter_note.subsections:
        for subsection in chapter_note.subsections:
            with st.expander(subsection.title):
                st.write(subsection.summary)

                if subsection.key_points:
                    st.markdown("**重點：**")

                    for point in subsection.key_points:
                        st.write(f"- {point}")

                if subsection.important_terms:
                    st.markdown("**術語：**")

                    for term in subsection.important_terms:
                        st.write(f"- {term}")
    else:
        st.info("這個主章節沒有子章節整理。")

    st.subheader("🖼️ PDF 圖片與畫面解讀")

    if chapter_note.image_insights:
        visual_contexts = st.session_state.get(
            "chapter_visual_contexts",
            {},
        )

        selected_chapter_note_id = st.session_state.get(
            "selected_chapter_note_id"
        )

        current_visual_context = visual_contexts.get(
            selected_chapter_note_id,
            [],
        )

        image_url_map = {
            item.get("page_number"): item.get("image_data_url")
            for item in current_visual_context
            if item.get("image_data_url")
        }

        for image in chapter_note.image_insights:
            with st.expander(
                f"第 {image.page_number} 頁｜{image.title}"
            ):
                image_data_url = image_url_map.get(image.page_number)

                if image_data_url:
                    st.image(
                        image_data_url,
                        caption=f"PDF 第 {image.page_number} 頁",
                        use_container_width=True,
                    )
                else:
                    st.caption("此頁沒有保留可顯示的圖片資料。")

                st.caption(f"圖片類型：{image.image_type}")
                st.write(image.description)

                if image.related_subsection:
                    st.info(
                        f"對應子章節：{image.related_subsection}"
                    )

                if image.learning_points:
                    st.markdown("**從圖片可學到：**")

                    for point in image.learning_points:
                        st.write(f"- {point}")
    else:
        st.info("這次沒有偵測到需要補充的圖片教學資訊。")

    st.subheader("🧪 練習建議")

    if chapter_note.practice_tips:
        for index, tip in enumerate(
            chapter_note.practice_tips,
            start=1,
        ):
            with st.expander(f"練習 {index}｜{tip.title}"):
                st.write(f"操作：{tip.instruction}")

                if tip.expected_result:
                    st.success(
                        f"預期成果：{tip.expected_result}"
                    )
    else:
        st.info("這次沒有產生練習建議。")

    st.subheader("🗺️ 章節學習地圖")

    is_mermaid_valid, mermaid_error = validate_mermaid(
        chapter_note.mermaid
    )

    if is_mermaid_valid:
        st.code(
            chapter_note.mermaid,
            language="text",
        )
    else:
        st.warning(f"Mermaid 圖表無法使用：{mermaid_error}")

    st.subheader("❓ 章節 Quiz")

    if chapter_note.quiz:
        for index, item in enumerate(
            chapter_note.quiz,
            start=1,
        ):
            with st.expander(f"第 {index} 題"):
                st.write(f"Q：{item.question}")
                st.write(f"A：{item.answer}")

                if item.explanation:
                    st.write(f"說明：{item.explanation}")
    else:
        st.info("這次沒有產生 Quiz。")

    st.subheader("🗂️ 章節 Flash Cards")

    if chapter_note.flashcards:
        for index, card in enumerate(
            chapter_note.flashcards,
            start=1,
        ):
            with st.expander(f"Flash Card {index}"):
                st.write(f"正面：{card.front}")
                st.write(f"背面：{card.back}")
    else:
        st.info("這次沒有產生 Flash Cards。")


def show_final_result(document_name: str) -> None:
    """顯示完整文件分析結果與匯出功能。"""

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
        for index, item in enumerate(
            final_result.quiz,
            start=1,
        ):
            with st.expander(f"第 {index} 題"):
                st.write(f"Q：{item.question}")
                st.write(f"A：{item.answer}")
    else:
        st.info("這次沒有產生 Quiz。")

    st.subheader("🗂️ Flash Cards")

    if final_result.flashcards:
        for index, card in enumerate(
            final_result.flashcards,
            start=1,
        ):
            with st.expander(f"Flash Card {index}"):
                st.write(f"正面：{card.front}")
                st.write(f"背面：{card.back}")
    else:
        st.info("這次沒有產生 Flash Cards。")

    st.divider()
    st.subheader("📤 匯出結果")

    if st.button(
        "建立 Notion 筆記頁面",
        type="primary",
    ):
        with st.spinner("正在建立 Notion 筆記頁面..."):
            try:
                notion_page_url = create_notion_page(
                    document_name=document_name,
                    analysis_result=final_result,
                )

                st.session_state["notion_page_url"] = notion_page_url
                st.success("Notion 筆記頁面建立完成。")

            except Exception as error:
                st.error(f"建立 Notion 頁面失敗：{error}")

    if "notion_page_url" in st.session_state:
        st.link_button(
            "開啟 Notion 筆記頁面",
            st.session_state["notion_page_url"],
        )

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


def _show_single_export_estimate(
    title: str,
    estimate: dict,
    is_resume_mode: bool,
) -> None:
    """顯示單一匯出模式的預估資訊。"""

    st.markdown(f"#### {title}")

    if estimate["chapter_count"] == 0:
        st.info("目前沒有可匯出的主章節。")
        return

    if not is_resume_mode:
        row1_col1, row1_col2, row1_col3 = st.columns(3)

        row1_col1.metric(
            "主章節總數",
            estimate["chapter_count"],
        )

        row1_col2.metric(
            "預估 AI 呼叫次數",
            estimate["estimated_api_calls"],
        )

        row1_col3.metric(
            "預估總 Token",
            estimate["estimated_total_tokens_text"],
        )

        row2_col1, row2_col2, row2_col3 = st.columns(3)

        row2_col1.metric(
            "本次預計分析圖片",
            f"{estimate['need_visual_analysis_page_count']} 張",
        )

        row2_col2.metric(
            "本次預計生成詳細筆記",
            f"{estimate['need_note_generation_count']} 份",
        )

        row2_col3.metric(
            "預估輸入 Token",
            estimate["estimated_input_tokens_text"],
        )

        row3_col1, row3_col2 = st.columns(2)

        row3_col1.metric(
            "預估輸出 Token",
            estimate["estimated_output_tokens_text"],
        )

        row3_col2.metric(
            "已有詳細筆記快取",
            f"{estimate['note_cache_count']} 份",
        )

        st.info(
            f"預估處理時間：**{estimate['estimated_time_text']}**"
        )

        st.caption(
            "本次預計分析圖片：本次會建立的 PDF 圖片分析快取頁數。"
        )

        st.caption(
            "本次預計生成詳細筆記：本次會建立的 Module 詳細筆記快取數。"
        )

        return

    top_col1, top_col2, top_col3 = st.columns(3)

    top_col1.metric(
        "主章節總數",
        estimate["chapter_count"],
    )

    top_col2.metric(
        "本次需處理",
        estimate["pending_count"],
    )

    top_col3.metric(
        "預估 AI 呼叫次數",
        estimate["estimated_api_calls"],
    )

    token_col1, token_col2, token_col3 = st.columns(3)

    token_col1.metric(
        "預估輸入 Token",
        estimate["estimated_input_tokens_text"],
    )

    token_col2.metric(
        "預估輸出 Token",
        estimate["estimated_output_tokens_text"],
    )

    token_col3.metric(
        "預估總 Token",
        estimate["estimated_total_tokens_text"],
    )

    detail_col1, detail_col2, detail_col3 = st.columns(3)

    detail_col1.metric(
        "本次預計分析圖片",
        f"{estimate['need_visual_analysis_page_count']} 張",
    )

    detail_col2.metric(
        "本次預計生成詳細筆記",
        f"{estimate['need_note_generation_count']} 份",
    )

    detail_col3.metric(
        "已有詳細筆記快取",
        f"{estimate['note_cache_count']} 份",
    )

    st.info(
        f"預估處理時間：**{estimate['estimated_time_text']}**"
    )

    if estimate["pending_count"] == 0:
        st.success("所有 Module 已完成，不需要再續跑。")
    else:
        st.caption(
            f"已完成 {estimate['completed_count']} 個 Module，"
            "續跑時會跳過已成功建立的章節。"
        )


def show_export_estimates(
    document_name: str,
    chapters: list[dict],
    parsed_document: dict,
) -> None:
    """顯示續跑與完整匯出的預估。"""

    st.subheader("⏱️ 匯出前預估")

    resume_estimate = estimate_document_export(
        document_name=document_name,
        chapters=chapters,
        parsed_document=parsed_document,
        resume=True,
    )

    new_export_estimate = estimate_document_export(
        document_name=document_name,
        chapters=chapters,
        parsed_document=parsed_document,
        resume=False,
    )

    with st.expander(
        "繼續未完成的 Notion 匯出預估",
        expanded=True,
    ):
        _show_single_export_estimate(
            title="續跑模式",
            estimate=resume_estimate,
            is_resume_mode=True,
        )

    with st.expander(
        "開始整份 Notion 匯出預估",
        expanded=False,
    ):
        _show_single_export_estimate(
            title="全新 Notion 匯出模式",
            estimate=new_export_estimate,
            is_resume_mode=False,
        )


def run_document_notion_export(
    document_name: str,
    chapters: list[dict],
    parsed_document: dict,
    resume: bool,
) -> None:
    """執行整份文件 Notion 匯出並顯示進度。"""

    current_document_id = st.session_state.get(
        "current_document_id"
    )

    if current_document_id:
        mark_document_exporting(current_document_id)

    progress_bar = st.progress(0)
    progress_status = st.empty()

    def update_progress(
        current: int,
        total: int,
        message: str,
    ) -> None:
        progress_value = int((current / total) * 100)

        progress_bar.progress(
            progress_value,
            text=message,
        )

        progress_status.caption(
            f"進度：{current} / {total} 個主章節"
        )

    try:
        export_result = create_document_learning_notebook(
            document_name=document_name,
            chapters=chapters,
            parsed_document=parsed_document,
            progress_callback=update_progress,
            max_visual_pages=3,
            resume=resume,
        )

        st.session_state["document_notion_result"] = export_result

        if current_document_id:
            update_document_export_result(
                document_id=current_document_id,
                export_result=export_result,
            )

        progress_bar.progress(
            100,
            text="整份 Notion 詳細學習筆記處理完成。",
        )

        completed_count = len(
            export_result.get("completed_chapters", [])
        )

        failed_count = len(
            export_result.get("failed_chapters", [])
        )

        processed_count = export_result.get(
            "processed_chapter_count",
            0,
        )

        cached_visual_count = export_result.get(
            "cached_visual_count",
            0,
        )

        cached_note_count = export_result.get(
            "cached_note_count",
            0,
        )

        if export_result.get("is_finished", False):
            st.success(
                f"完成：共建立 {completed_count} 個 Module 子頁面。"
            )
        elif failed_count:
            st.warning(
                f"本次處理 {processed_count} 個 Module；"
                f"目前成功 {completed_count} 個，"
                f"仍有 {failed_count} 個未完成。"
            )
        else:
            st.info("本次沒有需要執行的章節。")

        cache_col1, cache_col2 = st.columns(2)

        cache_col1.metric(
            "本次使用圖片分析快取",
            f"{cached_visual_count} 個 Module",
        )

        cache_col2.metric(
            "本次使用詳細筆記快取",
            f"{cached_note_count} 個 Module",
        )

        if cached_visual_count or cached_note_count:
            st.info(
                "已直接讀取快取資料，對應 Module 不會重新進行 AI 分析。"
            )

    except Exception as error:
        progress_bar.empty()
        progress_status.empty()
        st.error(f"整份 Notion 詳細學習筆記建立失敗：{error}")


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

if uploaded_file is None and "parsed_document" not in st.session_state:
    st.info("請先上傳 PDF、DOCX、TXT 或 Markdown 檔案。")

if uploaded_file is not None:
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

                file_bytes = uploaded_file.getvalue()

                parsed_document = parse_uploaded_file(
                    uploaded_file,
                    extension,
                )

                raw_text = parsed_document["raw_text"]

                if not raw_text.strip():
                    st.warning("這份文件沒有可讀取的文字內容。")
                    st.stop()

                chapters = detect_chapters(raw_text)
                cleaned_text = clean_text(raw_text)
                chunks = chunk_text(cleaned_text)

                if not chunks:
                    st.warning("文件清理後沒有可供分析的內容。")
                    st.stop()

                file_hash = create_file_hash(file_bytes)

                database_document = create_or_update_document(
                    file_name=uploaded_file.name,
                    file_extension=extension,
                    file_size_bytes=uploaded_file.size,
                    file_hash=file_hash,
                    metadata=parsed_document["metadata"],
                    chapters=chapters,
                )

                st.session_state["current_file_name"] = uploaded_file.name
                st.session_state["current_document_id"] = database_document.id
                st.session_state["parsed_document"] = parsed_document
                st.session_state["cleaned_text"] = cleaned_text
                st.session_state["chapters"] = chapters
                st.session_state["chunks"] = chunks

                st.session_state.pop("chunk_result", None)
                st.session_state.pop("final_result", None)
                st.session_state.pop("all_chunk_results", None)
                st.session_state.pop("notion_page_url", None)
                st.session_state.pop("chapter_notes", None)
                st.session_state.pop("selected_chapter_note_id", None)
                st.session_state.pop("scroll_to_chapter_note", None)
                st.session_state.pop("chapter_visual_contexts", None)
                st.session_state.pop("document_notion_result", None)

                st.success("檔案解析、章節偵測與 SQLite 文件紀錄建立完成。")

            except Exception as error:
                st.error(f"文件處理失敗：{error}")

if "parsed_document" in st.session_state:
    parsed_document = st.session_state["parsed_document"]
    metadata = parsed_document["metadata"]
    cleaned_text = st.session_state["cleaned_text"]
    chapters = st.session_state.get("chapters", [])
    chunks = st.session_state["chunks"]

    current_file_name = st.session_state.get(
        "current_file_name",
        metadata.get("file_name", "未命名文件"),
    )

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

    if st.session_state.get("current_document_id"):
        st.caption(
            f"SQLite 文件 ID：{st.session_state['current_document_id']}"
        )

    st.text_area(
        "清理後文字預覽",
        value=cleaned_text,
        height=300,
    )

    st.divider()
    st.subheader("📚 章節偵測結果")

    st.metric("偵測到主章節數", len(chapters))

    if "chapter_notes" not in st.session_state:
        st.session_state["chapter_notes"] = {}

    if "chapter_visual_contexts" not in st.session_state:
        st.session_state["chapter_visual_contexts"] = {}

    if chapters:
        for chapter in chapters:
            chapter_id = chapter["chapter_id"]
            subsection_count = len(chapter.get("subsections", []))

            chapter_title = (
                f"第 {chapter_id} 章｜"
                f"{chapter['title']}"
            )

            with st.expander(chapter_title):
                current_document_id = st.session_state.get(
                    "current_document_id"
                )

                learning_item_counts = {
                    "quiz_count": 0,
                    "flashcard_count": 0,
                }

                if current_document_id:
                    learning_item_counts = count_chapter_learning_items(
                        document_id=current_document_id,
                        source_chapter_id=str(chapter_id),
                    )

                st.caption(
                    f"標題來源：{chapter['source']}｜"
                    f"子章節數：{subsection_count}｜"
                    f"字元數：{len(chapter['content'])}｜"
                    f"Quiz：{learning_item_counts['quiz_count']} 題｜"
                    f"Flash Cards：{learning_item_counts['flashcard_count']} 張"
                )

                st.text_area(
                    label=f"主章節內容預覽 {chapter_id}",
                    value=chapter["content"][:3000],
                    height=250,
                    key=f"chapter_preview_{chapter_id}",
                )

                if st.button(
                    "生成詳細學習筆記",
                    key=f"generate_chapter_note_{chapter_id}",
                ):
                    with st.spinner(
                        f"AI 正在整理 {chapter['title']}..."
                    ):
                        try:
                            visual_context = []

                            is_pdf = (
                                metadata.get("file_extension") == ".pdf"
                            )

                            has_pdf_data = (
                                parsed_document.get("pdf_bytes")
                                and parsed_document.get("page_texts")
                            )

                            if is_pdf and has_pdf_data:
                                visual_context = analyze_chapter_visuals(
                                    chapter=chapter,
                                    pdf_bytes=parsed_document["pdf_bytes"],
                                    page_texts=parsed_document[
                                        "page_texts"
                                    ],
                                    max_pages=3,
                                )

                                st.session_state[
                                    "chapter_visual_contexts"
                                ][chapter_id] = visual_context

                            chapter_note = analyze_chapter(
                                chapter=chapter,
                                visual_context=visual_context,
                            )

                            current_document_id = st.session_state.get(
                                "current_document_id"
                            )

                            if current_document_id:
                                save_result = save_chapter_learning_items(
                                    document_id=current_document_id,
                                    source_chapter_id=str(chapter_id),
                                    chapter_note=chapter_note,
                                )

                                if save_result["saved"]:
                                    st.success(
                                        "已寫入 SQLite："
                                        f"{save_result['quiz_count']} 題 Quiz、"
                                        f"{save_result['flashcard_count']} 張 Flash Cards。"
                                    )
                                else:
                                    st.warning(
                                        "Quiz / Flash Cards 未寫入 SQLite："
                                        f"{save_result['reason']}"
                                    )

                            st.session_state["chapter_notes"][
                                chapter_id
                            ] = chapter_note

                            st.session_state[
                                "selected_chapter_note_id"
                            ] = chapter_id

                            st.session_state[
                                "scroll_to_chapter_note"
                            ] = True

                            st.success("詳細學習筆記生成完成。")

                        except Exception as error:
                            st.error(
                                f"章節學習筆記生成失敗：{error}"
                            )

                if chapter_id in st.session_state["chapter_notes"]:
                    if st.button(
                        "查看這章詳細學習筆記",
                        key=f"view_chapter_note_{chapter_id}",
                    ):
                        st.session_state[
                            "selected_chapter_note_id"
                        ] = chapter_id

                        st.session_state[
                            "scroll_to_chapter_note"
                        ] = True

                subsections = chapter.get("subsections", [])

                if subsections:
                    st.markdown("#### 子章節")

                    for subsection in subsections:
                        subsection_title = (
                            f"{subsection['title']}｜"
                            f"{len(subsection['content'])} 字元"
                        )

                        with st.expander(subsection_title):
                            st.text_area(
                                label=(
                                    f"子章節內容預覽 "
                                    f"{chapter_id}_"
                                    f"{subsection['section_id']}"
                                ),
                                value=subsection["content"][:2000],
                                height=180,
                                key=(
                                    f"subsection_preview_"
                                    f"{chapter_id}_"
                                    f"{subsection['section_id']}"
                                ),
                            )
                else:
                    st.info("此主章節未偵測到明確子章節。")

        selected_chapter_note_id = st.session_state.get(
            "selected_chapter_note_id"
        )

        chapter_notes = st.session_state.get("chapter_notes", {})

        if selected_chapter_note_id in chapter_notes:
            st.markdown(
                '<div id="chapter-learning-note-detail"></div>',
                unsafe_allow_html=True,
            )

            if st.session_state.get("scroll_to_chapter_note"):
                components.html(
                    """
                    <script>
                        setTimeout(function() {
                            const target = window.parent.document.getElementById(
                                "chapter-learning-note-detail"
                            );

                            if (target) {
                                target.scrollIntoView({
                                    behavior: "smooth",
                                    block: "start"
                                });
                            }
                        }, 600);
                    </script>
                    """,
                    height=0,
                )

                st.session_state["scroll_to_chapter_note"] = False

            show_chapter_learning_note(
                chapter_notes[selected_chapter_note_id]
            )

    else:
        st.info("未偵測到明確章節，系統將整份文件視為單一章節。")

    st.divider()
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
    st.subheader("📚 整份文件分析與 Notion 匯出")

    current_document_id = st.session_state.get(
        "current_document_id"
    )

    if current_document_id:
        document_learning_counts = count_document_learning_items(
            current_document_id
        )

        learning_col1, learning_col2 = st.columns(2)

        learning_col1.metric(
            "已儲存 Quiz",
            f"{document_learning_counts['quiz_count']} 題",
        )

        learning_col2.metric(
            "已儲存 Flash Cards",
            f"{document_learning_counts['flashcard_count']} 張",
        )

    show_export_estimates(
        document_name=current_file_name,
        chapters=chapters,
        parsed_document=parsed_document,
    )

    analysis_col, resume_col, restart_col = st.columns(3)

    with analysis_col:
        if st.button(
            "分析整份文件",
            type="primary",
        ):
            with st.spinner("AI 正在分析所有內容並整合筆記..."):
                try:
                    final_result, chunk_results = analyze_document(chunks)

                    st.session_state["final_result"] = final_result
                    st.session_state["all_chunk_results"] = chunk_results
                    st.session_state.pop("notion_page_url", None)

                    st.success("完整文件分析完成。")

                except Exception as error:
                    st.error(f"完整文件分析失敗：{error}")

    with resume_col:
        if st.button(
            "繼續未完成的 Notion 匯出",
            type="primary",
        ):
            run_document_notion_export(
                document_name=current_file_name,
                chapters=chapters,
                parsed_document=parsed_document,
                resume=True,
            )

    with restart_col:
        if st.button(
            "開始整份 Notion 匯出",
            type="primary",
        ):
            run_document_notion_export(
                document_name=current_file_name,
                chapters=chapters,
                parsed_document=parsed_document,
                resume=False,
            )

    if "document_notion_result" in st.session_state:
        document_notion_result = st.session_state[
            "document_notion_result"
        ]

        st.link_button(
            "開啟 Notion 詳細學習筆記",
            document_notion_result["parent_page_url"],
        )

        result_col1, result_col2 = st.columns(2)

        result_col1.metric(
            "圖片分析快取",
            f"{document_notion_result.get('cached_visual_count', 0)} 個",
        )

        result_col2.metric(
            "詳細筆記快取",
            f"{document_notion_result.get('cached_note_count', 0)} 個",
        )

        failed_chapters = document_notion_result.get(
            "failed_chapters",
            [],
        )

        if failed_chapters:
            with st.expander("查看尚未完成章節"):
                for failed_chapter in failed_chapters:
                    st.error(
                        f"{failed_chapter.get('chapter_title', '未知章節')}："
                        f"{failed_chapter.get('error', '未知錯誤')}"
                    )

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

if "parsed_document" in st.session_state:
    current_file_name = st.session_state.get(
        "current_file_name",
        "未命名文件",
    )

    show_final_result(current_file_name)