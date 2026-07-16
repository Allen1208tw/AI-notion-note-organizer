from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from src.config.settings import OPENAI_MODEL, SUPPORTED_FILE_TYPES
from src.database.init_db import initialize_database
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
    sync_document_learning_cache_to_sqlite,
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

schema_issues = initialize_database()

if schema_issues:
    st.error(
        "SQLite 資料庫版本與目前程式不一致。請先備份 outputs 資料夾，"
        "再依資料管理說明執行資料庫升級。\n\n"
        + "\n".join(f"- {issue}" for issue in schema_issues)
    )
    st.stop()


def inject_full_text_css() -> None:
    """避免 Streamlit 元件文字被省略號截斷。"""

    st.markdown(
        """
        <style>
        html,
        body,
        [class*="css"] {
            white-space: normal !important;
            overflow-wrap: anywhere !important;
            word-break: break-word !important;
        }

        div[data-testid="stMarkdownContainer"],
        div[data-testid="stMarkdownContainer"] p,
        div[data-testid="stCaptionContainer"],
        div[data-testid="stText"] {
            white-space: normal !important;
            overflow: visible !important;
            text-overflow: clip !important;
            overflow-wrap: anywhere !important;
            word-break: break-word !important;
        }

        div[data-testid="stMetric"] {
            min-width: 0 !important;
            height: auto !important;
            overflow: visible !important;
        }

        div[data-testid="stMetric"] label,
        div[data-testid="stMetric"] label p,
        div[data-testid="stMetric"] [data-testid="stMetricLabel"],
        div[data-testid="stMetric"] [data-testid="stMetricLabel"] p,
        div[data-testid="stMetric"] [data-testid="stMetricValue"],
        div[data-testid="stMetric"] [data-testid="stMetricValue"] div {
            white-space: normal !important;
            overflow: visible !important;
            text-overflow: clip !important;
            overflow-wrap: anywhere !important;
            word-break: break-word !important;
            line-height: 1.35 !important;
            max-width: none !important;
            height: auto !important;
        }

        div[data-testid="stMetric"] [data-testid="stMetricLabel"] {
            min-height: 2.7em !important;
            align-items: flex-start !important;
        }

        div[data-testid="column"] {
            min-width: 0 !important;
        }

        button,
        button div,
        button p,
        a,
        a div,
        a p {
            white-space: normal !important;
            overflow: visible !important;
            text-overflow: clip !important;
            overflow-wrap: anywhere !important;
            word-break: break-word !important;
            height: auto !important;
        }

        details summary,
        details summary span,
        div[data-testid="stExpander"] summary,
        div[data-testid="stExpander"] summary p {
            white-space: normal !important;
            overflow: visible !important;
            text-overflow: clip !important;
            overflow-wrap: anywhere !important;
            word-break: break-word !important;
        }

        pre,
        code {
            white-space: pre-wrap !important;
            overflow-wrap: anywhere !important;
            word-break: break-word !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


inject_full_text_css()


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

    content = (
        f"**{getattr(callout, 'icon', '📌')} "
        f"{getattr(callout, 'title', '重點')}**\n\n"
        f"{getattr(callout, 'content', '')}"
    )

    tone = getattr(callout, "tone", "info")

    if tone == "warning":
        st.warning(content)
    elif tone == "success":
        st.success(content)
    else:
        st.info(content)


def show_comparison_table(table) -> None:
    """顯示 AI 回傳的比較表格。"""

    headers = getattr(table, "headers", []) or []
    rows = getattr(table, "rows", []) or []

    if not headers or not rows:
        return

    formatted_rows = []

    for row in rows:
        row_data = {}

        for index, header in enumerate(headers):
            row_data[header] = row[index] if index < len(row) else ""

        formatted_rows.append(row_data)

    st.markdown(
        f"#### 📊 {getattr(table, 'title', '重點比較')}"
    )
    st.table(formatted_rows)

    note = getattr(table, "note", "")

    if note:
        st.caption(f"補充：{note}")


def show_chunk_result() -> None:
    """顯示單一 Chunk 分析結果。"""

    if "chunk_result" not in st.session_state:
        return

    result = st.session_state["chunk_result"]

    st.divider()
    st.subheader("🤖 第一段 AI 分析結果")

    st.subheader("📌 段落摘要")
    st.write(
        getattr(
            result,
            "chunk_summary",
            "AI 沒有回傳摘要。",
        )
    )

    st.subheader("🧠 重點整理")

    key_points = getattr(result, "key_points", []) or []

    if key_points:
        for point in key_points:
            st.write(f"- {point}")
    else:
        st.info("這次 AI 沒有回傳重點整理。")

    st.subheader("📚 關鍵術語")

    terms = getattr(result, "terms", []) or []

    if terms:
        for term in terms:
            st.write(f"- {term}")
    else:
        st.info("這次 AI 沒有回傳關鍵術語。")

    st.subheader("❓ Quiz 題目素材")

    quiz_candidates = (
        getattr(result, "quiz_candidates", []) or []
    )

    if quiz_candidates:
        for item in quiz_candidates:
            st.write(
                f"Q：{getattr(item, 'question', '')}"
            )
            st.write(
                f"A：{getattr(item, 'answer', '')}"
            )
            st.divider()
    else:
        st.info("這次 AI 沒有回傳 Quiz 題目。")

    st.subheader("🗂️ Flash Card 素材")

    flashcards = (
        getattr(result, "flashcard_candidates", []) or []
    )

    if flashcards:
        for card in flashcards:
            st.write(
                f"正面：{getattr(card, 'front', '')}"
            )
            st.write(
                f"背面：{getattr(card, 'back', '')}"
            )
            st.divider()
    else:
        st.info("這次 AI 沒有回傳 Flash Card。")


def show_chapter_learning_note(chapter_note) -> None:
    """顯示單一 Module 的詳細學習筆記。"""

    chapter_title = getattr(
        chapter_note,
        "chapter_title",
        "未命名章節",
    )

    st.divider()
    st.header(f"📘 詳細學習筆記｜{chapter_title}")

    callout_notes = (
        getattr(chapter_note, "callout_notes", []) or []
    )

    if callout_notes:
        st.subheader("✨ 重點標註")

        for callout in callout_notes:
            show_callout(callout)

    st.subheader("🎯 學習目標")

    learning_objectives = (
        getattr(chapter_note, "learning_objectives", []) or []
    )

    if learning_objectives:
        for objective in learning_objectives:
            st.write(f"- {objective}")
    else:
        st.info("這次沒有產生學習目標。")

    st.subheader("📝 章節摘要")
    st.write(
        getattr(chapter_note, "chapter_summary", "")
    )

    st.subheader("🧠 白話講解")
    st.write(
        getattr(chapter_note, "plain_explanation", "")
    )

    st.subheader("⭐ 核心重點")

    key_points = (
        getattr(chapter_note, "key_points", []) or []
    )

    if key_points:
        for point in key_points:
            st.write(f"- {point}")
    else:
        st.info("這次沒有產生核心重點。")

    st.subheader("📚 重要術語")

    important_terms = (
        getattr(chapter_note, "important_terms", []) or []
    )

    if important_terms:
        for term in important_terms:
            st.write(f"- {term}")
    else:
        st.info("這次沒有產生重要術語。")

    st.subheader("📌 語法規則與注意事項")

    syntax_rules = (
        getattr(chapter_note, "syntax_rules", []) or []
    )

    if syntax_rules:
        for rule in syntax_rules:
            st.write(f"- {rule}")
    else:
        st.info("這次沒有產生語法規則。")

    comparison_tables = (
        getattr(chapter_note, "comparison_tables", []) or []
    )

    if comparison_tables:
        st.subheader("📊 重點比較表")

        for table in comparison_tables:
            show_comparison_table(table)

    st.subheader("💻 程式碼範例")

    code_examples = (
        getattr(chapter_note, "code_examples", []) or []
    )

    if code_examples:
        for index, example in enumerate(
            code_examples,
            start=1,
        ):
            title = getattr(
                example,
                "title",
                f"範例 {index}",
            )

            with st.expander(f"範例 {index}｜{title}"):
                st.code(
                    getattr(example, "code", ""),
                    language=getattr(
                        example,
                        "language",
                        "text",
                    ),
                )
                st.write(
                    getattr(example, "explanation", "")
                )
    else:
        st.info("這個章節沒有產生程式碼範例。")

    st.subheader("⚠️ 常見錯誤與混淆")

    common_mistakes = (
        getattr(chapter_note, "common_mistakes", []) or []
    )

    if common_mistakes:
        for index, mistake in enumerate(
            common_mistakes,
            start=1,
        ):
            with st.expander(f"常見錯誤 {index}"):
                st.write(
                    f"容易出錯："
                    f"{getattr(mistake, 'mistake', '')}"
                )
                st.write(
                    f"正確觀念："
                    f"{getattr(mistake, 'correction', '')}"
                )
    else:
        st.info("這次沒有產生常見錯誤提醒。")

    st.subheader("🧩 子章節整理")

    subsections = (
        getattr(chapter_note, "subsections", []) or []
    )

    if subsections:
        for subsection in subsections:
            with st.expander(
                getattr(subsection, "title", "未命名子章節")
            ):
                st.write(
                    getattr(subsection, "summary", "")
                )

                subsection_points = (
                    getattr(
                        subsection,
                        "key_points",
                        [],
                    )
                    or []
                )

                if subsection_points:
                    st.markdown("**重點：**")

                    for point in subsection_points:
                        st.write(f"- {point}")

                subsection_terms = (
                    getattr(
                        subsection,
                        "important_terms",
                        [],
                    )
                    or []
                )

                if subsection_terms:
                    st.markdown("**術語：**")

                    for term in subsection_terms:
                        st.write(f"- {term}")
    else:
        st.info("這個主章節沒有子章節整理。")

    st.subheader("🖼️ PDF 圖片與畫面解讀")

    image_insights = (
        getattr(chapter_note, "image_insights", []) or []
    )

    if image_insights:
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
            item.get("page_number"): item.get(
                "image_data_url"
            )
            for item in current_visual_context
            if isinstance(item, dict)
            and item.get("image_data_url")
        }

        for image in image_insights:
            page_number = getattr(
                image,
                "page_number",
                "?",
            )

            title = getattr(
                image,
                "title",
                "圖片解讀",
            )

            with st.expander(
                f"第 {page_number} 頁｜{title}"
            ):
                image_data_url = image_url_map.get(
                    page_number
                )

                if image_data_url:
                    st.image(
                        image_data_url,
                        caption=f"PDF 第 {page_number} 頁",
                        width="stretch",
                    )
                else:
                    st.caption(
                        "此頁沒有保留可顯示的圖片資料。"
                    )

                st.caption(
                    f"圖片類型："
                    f"{getattr(image, 'image_type', '')}"
                )

                st.write(
                    getattr(image, "description", "")
                )

                related_subsection = getattr(
                    image,
                    "related_subsection",
                    "",
                )

                if related_subsection:
                    st.info(
                        f"對應子章節：{related_subsection}"
                    )

                learning_points = (
                    getattr(
                        image,
                        "learning_points",
                        [],
                    )
                    or []
                )

                if learning_points:
                    st.markdown("**從圖片可學到：**")

                    for point in learning_points:
                        st.write(f"- {point}")
    else:
        st.info(
            "這次沒有偵測到需要補充的圖片教學資訊。"
        )

    st.subheader("🧪 練習建議")

    practice_tips = (
        getattr(chapter_note, "practice_tips", []) or []
    )

    if practice_tips:
        for index, tip in enumerate(
            practice_tips,
            start=1,
        ):
            title = getattr(
                tip,
                "title",
                f"練習 {index}",
            )

            with st.expander(f"練習 {index}｜{title}"):
                st.write(
                    f"操作："
                    f"{getattr(tip, 'instruction', '')}"
                )

                expected_result = getattr(
                    tip,
                    "expected_result",
                    "",
                )

                if expected_result:
                    st.success(
                        f"預期成果：{expected_result}"
                    )
    else:
        st.info("這次沒有產生練習建議。")

    st.subheader("🗺️ 章節學習地圖")

    mermaid = getattr(chapter_note, "mermaid", "")
    is_mermaid_valid, mermaid_error = (
        validate_mermaid(mermaid)
    )

    if is_mermaid_valid:
        st.code(
            mermaid,
            language="text",
        )
    else:
        st.warning(
            f"Mermaid 圖表無法使用：{mermaid_error}"
        )

    st.subheader("❓ 章節 Quiz")

    quiz_items = (
        getattr(chapter_note, "quiz", []) or []
    )

    if quiz_items:
        for index, item in enumerate(
            quiz_items,
            start=1,
        ):
            with st.expander(f"第 {index} 題"):
                st.write(
                    f"Q：{getattr(item, 'question', '')}"
                )
                st.write(
                    f"A：{getattr(item, 'answer', '')}"
                )

                explanation = getattr(
                    item,
                    "explanation",
                    "",
                )

                if explanation:
                    st.write(f"說明：{explanation}")
    else:
        st.info("這次沒有產生 Quiz。")

    st.subheader("🗂️ 章節 Flash Cards")

    flashcards = (
        getattr(chapter_note, "flashcards", []) or []
    )

    if flashcards:
        for index, card in enumerate(
            flashcards,
            start=1,
        ):
            with st.expander(f"Flash Card {index}"):
                st.write(
                    f"正面：{getattr(card, 'front', '')}"
                )
                st.write(
                    f"背面：{getattr(card, 'back', '')}"
                )
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
    st.write(getattr(final_result, "summary", ""))

    st.subheader("🧠 重點整理")

    key_points = (
        getattr(final_result, "key_points", []) or []
    )

    if key_points:
        for point in key_points:
            st.write(f"- {point}")
    else:
        st.info("這次沒有產生重點整理。")

    st.subheader("🗺️ Mermaid 圖表")

    mermaid = getattr(final_result, "mermaid", "")
    is_mermaid_valid, mermaid_error = (
        validate_mermaid(mermaid)
    )

    if is_mermaid_valid:
        st.code(
            mermaid,
            language="text",
        )
    else:
        st.warning(
            f"Mermaid 圖表無法使用：{mermaid_error}"
        )

    st.subheader("❓ Quiz")

    quiz_items = (
        getattr(final_result, "quiz", []) or []
    )

    if quiz_items:
        for index, item in enumerate(
            quiz_items,
            start=1,
        ):
            with st.expander(f"第 {index} 題"):
                st.write(
                    f"Q：{getattr(item, 'question', '')}"
                )
                st.write(
                    f"A：{getattr(item, 'answer', '')}"
                )
    else:
        st.info("這次沒有產生 Quiz。")

    st.subheader("🗂️ Flash Cards")

    flashcards = (
        getattr(final_result, "flashcards", []) or []
    )

    if flashcards:
        for index, card in enumerate(
            flashcards,
            start=1,
        ):
            with st.expander(f"Flash Card {index}"):
                st.write(
                    f"正面：{getattr(card, 'front', '')}"
                )
                st.write(
                    f"背面：{getattr(card, 'back', '')}"
                )
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

                st.session_state[
                    "notion_page_url"
                ] = notion_page_url

                st.success(
                    "Notion 筆記頁面建立完成。"
                )

            except Exception as error:
                st.error(
                    f"建立 Notion 頁面失敗：{error}"
                )

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


def _safe_int(value, default: int = 0) -> int:
    """安全轉成整數。"""

    try:
        if value is None:
            return default

        return int(value)
    except (TypeError, ValueError):
        return default


def _normalize_export_items(items) -> list:
    """將匯出結果安全轉換成 List。"""

    if items is None:
        return []

    if isinstance(items, list):
        return items

    if isinstance(items, (tuple, set)):
        return list(items)

    return [items]


def _get_export_chapter_id(item) -> str:
    """從不同格式的匯出結果取得章節 ID。"""

    if isinstance(item, dict):
        value = (
            item.get("chapter_id")
            or item.get("source_chapter_id")
            or item.get("chapter_order")
            or item.get("id")
        )

        return (
            str(value).strip()
            if value is not None
            else ""
        )

    if isinstance(item, (str, int)):
        return str(item).strip()

    value = (
        getattr(item, "chapter_id", None)
        or getattr(item, "source_chapter_id", None)
        or getattr(item, "chapter_order", None)
        or getattr(item, "id", None)
    )

    return (
        str(value).strip()
        if value is not None
        else ""
    )


def _get_source_chapter_id(chapter, index: int) -> str:
    """取得原始章節 ID。"""

    if isinstance(chapter, dict):
        value = (
            chapter.get("chapter_id")
            or chapter.get("source_chapter_id")
            or chapter.get("chapter_order")
            or index
        )
    else:
        value = (
            getattr(chapter, "chapter_id", None)
            or getattr(
                chapter,
                "source_chapter_id",
                None,
            )
            or getattr(chapter, "chapter_order", None)
            or index
        )

    return str(value).strip()


def _failed_item_has_real_error(item) -> bool:
    """判斷失敗項目是否有實際錯誤訊息。"""

    if not isinstance(item, dict):
        return False

    error_message = str(
        item.get("error")
        or item.get("message")
        or item.get("reason")
        or ""
    ).strip()

    return bool(error_message)


def _calculate_export_summary(
    export_result: dict,
    chapters: list[dict],
) -> dict:
    """
    計算 Notion 匯出摘要。

    規則：
    1. 成功章節優先於舊失敗紀錄。
    2. 支援字串、整數、字典及物件格式。
    3. is_finished=True 時，全部章節視為成功。
    4. 本次處理 0 個但續跑預估已無待處理章節時，
       視為所有章節早已完成。
    5. 不會僅因父頁面存在，就誤判所有子頁面成功。
    """

    if not isinstance(export_result, dict):
        export_result = {}

    chapters = chapters or []
    total_count = len(chapters)

    all_chapter_ids = {
        _get_source_chapter_id(chapter, index)
        for index, chapter in enumerate(
            chapters,
            start=1,
        )
    }

    completed_items = _normalize_export_items(
        export_result.get("completed_chapters")
    )

    failed_items = _normalize_export_items(
        export_result.get("failed_chapters")
    )

    completed_ids = {
        chapter_id
        for chapter_id in (
            _get_export_chapter_id(item)
            for item in completed_items
        )
        if chapter_id
    }

    failed_ids = {
        chapter_id
        for chapter_id in (
            _get_export_chapter_id(item)
            for item in failed_items
        )
        if chapter_id
    }

    if all_chapter_ids:
        completed_ids &= all_chapter_ids
        failed_ids &= all_chapter_ids

    actual_failed_ids = failed_ids - completed_ids

    processed_count = _safe_int(
        export_result.get(
            "processed_chapter_count",
            0,
        )
    )

    reported_completed_count = _safe_int(
        export_result.get(
            "completed_chapter_count",
            0,
        )
    )

    reported_failed_count = _safe_int(
        export_result.get(
            "failed_chapter_count",
            0,
        )
    )

    reported_pending_count = _safe_int(
        export_result.get(
            "pending_chapter_count",
            0,
        )
    )

    is_finished = bool(
        export_result.get("is_finished", False)
    )

    cached_note_count = _safe_int(
        export_result.get(
            "cached_note_count",
            0,
        )
    )

    parent_page_url = str(
        export_result.get("parent_page_url")
        or export_result.get("notion_parent_url")
        or ""
    ).strip()

    parent_page_id = str(
        export_result.get("parent_page_id")
        or export_result.get("notion_parent_page_id")
        or ""
    ).strip()

    has_notion_parent = bool(
        parent_page_url or parent_page_id
    )

    # 續跑時若所有 Module 都命中完整詳細筆記快取，
    # 且既有 Notion 父頁面仍存在，代表沒有 Module 需要重做。
    #
    # 舊版匯出狀態可能沒有回填 completed_chapters，
    # 因而錯誤顯示「成功 0、等待全部」。
    if (
        total_count > 0
        and processed_count == 0
        and cached_note_count >= total_count
        and has_notion_parent
        and reported_failed_count == 0
        and not any(
            _failed_item_has_real_error(item)
            for item in failed_items
        )
    ):
        completed_ids = set(all_chapter_ids)
        actual_failed_ids = set()
        reported_completed_count = total_count
        reported_pending_count = 0
        is_finished = True

    # Service 明確表示完成時，以完整章節數為準。
    if is_finished and total_count > 0:
        completed_ids = set(all_chapter_ids)
        actual_failed_ids = set()

    # 續跑時可能沒有重新處理任何章節，但狀態服務已判定沒有待處理。
    if (
        total_count > 0
        and processed_count == 0
        and reported_pending_count == 0
        and reported_failed_count == 0
        and reported_completed_count >= total_count
    ):
        completed_ids = set(all_chapter_ids)
        actual_failed_ids = set()
        is_finished = True

    # 某些舊版會保留 failed_chapters，但同時回報已完成總數。
    if (
        total_count > 0
        and reported_completed_count >= total_count
    ):
        completed_ids = set(all_chapter_ids)
        actual_failed_ids = set()
        is_finished = True

    # failed_chapters 只有舊章節 ID、沒有實際 error，
    # 且回傳明確表示已完成時，不再顯示為失敗。
    has_real_failed_error = any(
        _failed_item_has_real_error(item)
        for item in failed_items
    )

    if (
        is_finished
        and not has_real_failed_error
        and total_count > 0
    ):
        completed_ids = set(all_chapter_ids)
        actual_failed_ids = set()

    completed_count = len(completed_ids)
    failed_count = len(actual_failed_ids)

    # 向下相容只回傳數字、未回傳章節清單的 Service。
    if completed_count == 0:
        completed_count = min(
            reported_completed_count,
            total_count,
        )

    if failed_count == 0 and not is_finished:
        failed_count = min(
            reported_failed_count,
            max(total_count - completed_count, 0),
        )

    pending_count = max(
        total_count - completed_count - failed_count,
        0,
    )

    if is_finished and total_count > 0:
        completed_count = total_count
        failed_count = 0
        pending_count = 0

    if (
        total_count > 0
        and completed_count >= total_count
    ):
        completed_count = total_count
        failed_count = 0
        pending_count = 0
        is_finished = True
        actual_failed_ids = set()

    actual_failed_items = []

    for item in failed_items:
        chapter_id = _get_export_chapter_id(item)

        if chapter_id in actual_failed_ids:
            actual_failed_items.append(item)

    return {
        "total_count": total_count,
        "processed_count": max(processed_count, 0),
        "completed_count": completed_count,
        "failed_count": failed_count,
        "pending_count": pending_count,
        "is_finished": is_finished,
        "completed_chapter_ids": sorted(
            completed_ids
        ),
        "failed_chapter_ids": sorted(
            actual_failed_ids
        ),
        "failed_chapters": actual_failed_items,
    }


def _apply_export_summary_to_result(
    export_result: dict,
    export_summary: dict,
) -> dict:
    """把補正後的統計結果寫回匯出結果。"""

    normalized_result = dict(export_result)

    normalized_result["is_finished"] = (
        export_summary["is_finished"]
    )

    normalized_result["completed_chapter_count"] = (
        export_summary["completed_count"]
    )

    normalized_result["failed_chapter_count"] = (
        export_summary["failed_count"]
    )

    normalized_result["pending_chapter_count"] = (
        export_summary["pending_count"]
    )

    normalized_result["failed_chapters"] = (
        export_summary["failed_chapters"]
    )

    # 當原始 completed_chapters 缺失，但統計已確認完成，
    # 補成字串章節 ID，讓 SQLite 同步函式也能正確處理。
    if export_summary["completed_chapter_ids"]:
        original_completed = _normalize_export_items(
            normalized_result.get(
                "completed_chapters"
            )
        )

        original_completed_ids = {
            _get_export_chapter_id(item)
            for item in original_completed
            if _get_export_chapter_id(item)
        }

        if not original_completed_ids:
            normalized_result["completed_chapters"] = [
                {
                    "chapter_id": chapter_id,
                }
                for chapter_id in export_summary[
                    "completed_chapter_ids"
                ]
            ]

    return normalized_result


def _show_failed_export_chapter(
    failed_chapter,
) -> None:
    """安全顯示匯出失敗章節。"""

    if isinstance(failed_chapter, dict):
        chapter_title = str(
            failed_chapter.get("chapter_title")
            or failed_chapter.get("title")
            or failed_chapter.get("chapter_id")
            or failed_chapter.get(
                "source_chapter_id"
            )
            or "未知章節"
        )

        error_message = str(
            failed_chapter.get("error")
            or failed_chapter.get("message")
            or failed_chapter.get("reason")
            or "匯出未完成"
        )
    else:
        chapter_title = str(failed_chapter)
        error_message = "匯出未完成"

    st.error(
        f"{chapter_title}：{error_message}"
    )


def _show_single_export_estimate(
    title: str,
    estimate: dict,
    is_resume_mode: bool,
) -> None:
    """顯示單一匯出模式的預估資訊。"""

    estimate = (
        estimate
        if isinstance(estimate, dict)
        else {}
    )

    chapter_count = _safe_int(
        estimate.get("chapter_count", 0)
    )

    st.markdown(f"#### {title}")

    if chapter_count == 0:
        st.info("目前沒有可匯出的主章節。")
        return

    if not is_resume_mode:
        row1_col1, row1_col2, row1_col3 = (
            st.columns(3)
        )

        row1_col1.metric(
            "主章節總數",
            chapter_count,
        )

        row1_col2.metric(
            "預估 AI 呼叫次數",
            estimate.get(
                "estimated_api_calls",
                0,
            ),
        )

        row1_col3.metric(
            "預估總 Token",
            estimate.get(
                "estimated_total_tokens_text",
                "0",
            ),
        )

        row2_col1, row2_col2, row2_col3 = (
            st.columns(3)
        )

        row2_col1.metric(
            "本次預計分析圖片",
            f"{estimate.get('need_visual_analysis_page_count', 0)} 張",
        )

        row2_col2.metric(
            "本次預計生成詳細筆記",
            f"{estimate.get('need_note_generation_count', 0)} 份",
        )

        row2_col3.metric(
            "預估輸入 Token",
            estimate.get(
                "estimated_input_tokens_text",
                "0",
            ),
        )

        row3_col1, row3_col2 = st.columns(2)

        row3_col1.metric(
            "預估輸出 Token",
            estimate.get(
                "estimated_output_tokens_text",
                "0",
            ),
        )

        row3_col2.metric(
            "已有詳細筆記快取",
            f"{estimate.get('note_cache_count', 0)} 份",
        )

        st.info(
            "預估處理時間："
            f"**{estimate.get('estimated_time_text', '未知')}**"
        )

        st.caption(
            "本次預計分析圖片：本次會建立的 "
            "PDF 圖片分析快取頁數。"
        )

        st.caption(
            "本次預計生成詳細筆記：本次會建立的 "
            "Module 詳細筆記快取數。"
        )

        return

    top_col1, top_col2, top_col3 = st.columns(3)

    top_col1.metric(
        "主章節總數",
        chapter_count,
    )

    top_col2.metric(
        "本次需處理",
        estimate.get("pending_count", 0),
    )

    top_col3.metric(
        "預估 AI 呼叫次數",
        estimate.get(
            "estimated_api_calls",
            0,
        ),
    )

    token_col1, token_col2, token_col3 = (
        st.columns(3)
    )

    token_col1.metric(
        "預估輸入 Token",
        estimate.get(
            "estimated_input_tokens_text",
            "0",
        ),
    )

    token_col2.metric(
        "預估輸出 Token",
        estimate.get(
            "estimated_output_tokens_text",
            "0",
        ),
    )

    token_col3.metric(
        "預估總 Token",
        estimate.get(
            "estimated_total_tokens_text",
            "0",
        ),
    )

    detail_col1, detail_col2, detail_col3 = (
        st.columns(3)
    )

    detail_col1.metric(
        "本次預計分析圖片",
        f"{estimate.get('need_visual_analysis_page_count', 0)} 張",
    )

    detail_col2.metric(
        "本次預計生成詳細筆記",
        f"{estimate.get('need_note_generation_count', 0)} 份",
    )

    detail_col3.metric(
        "已有詳細筆記快取",
        f"{estimate.get('note_cache_count', 0)} 份",
    )

    st.info(
        "預估處理時間："
        f"**{estimate.get('estimated_time_text', '未知')}**"
    )

    if _safe_int(
        estimate.get("pending_count", 0)
    ) == 0:
        st.success(
            "所有 Module 已完成，不需要再續跑。"
        )
    else:
        st.caption(
            f"已完成 "
            f"{estimate.get('completed_count', 0)} "
            "個 Module，續跑時會跳過已成功建立的章節。"
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

    st.session_state[
        "resume_export_estimate"
    ] = resume_estimate

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
        mark_document_exporting(
            current_document_id
        )

    progress_bar = st.progress(0)
    progress_status = st.empty()

    def update_progress(
        current: int,
        total: int,
        message: str,
    ) -> None:
        safe_total = max(
            _safe_int(total, 1),
            1,
        )

        safe_current = min(
            max(_safe_int(current), 0),
            safe_total,
        )

        progress_value = int(
            (safe_current / safe_total) * 100
        )

        progress_bar.progress(
            progress_value,
            text=message,
        )

        progress_status.caption(
            f"進度：{safe_current} / "
            f"{safe_total} 個主章節"
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

        if not isinstance(export_result, dict):
            raise TypeError(
                "Notion 匯出結果格式錯誤，預期為 dict。"
            )

        export_summary = _calculate_export_summary(
            export_result=export_result,
            chapters=chapters,
        )

        # 如果是續跑，而且預估已顯示沒有待處理章節，
        # 但舊 Service 回傳 0 成功、舊失敗清單，
        # 則以「續跑前狀態已全部完成」為準。
        resume_estimate = st.session_state.get(
            "resume_export_estimate",
            {},
        )

        if (
            resume
            and isinstance(resume_estimate, dict)
            and _safe_int(
                resume_estimate.get(
                    "chapter_count",
                    0,
                )
            )
            == len(chapters)
            and _safe_int(
                resume_estimate.get(
                    "pending_count",
                    0,
                )
            )
            == 0
            and _safe_int(
                resume_estimate.get(
                    "completed_count",
                    0,
                )
            )
            >= len(chapters)
        ):
            export_summary[
                "completed_count"
            ] = len(chapters)

            export_summary[
                "failed_count"
            ] = 0

            export_summary[
                "pending_count"
            ] = 0

            export_summary[
                "is_finished"
            ] = True

            export_summary[
                "completed_chapter_ids"
            ] = [
                _get_source_chapter_id(
                    chapter,
                    index,
                )
                for index, chapter in enumerate(
                    chapters,
                    start=1,
                )
            ]

            export_summary[
                "failed_chapter_ids"
            ] = []

            export_summary[
                "failed_chapters"
            ] = []

        normalized_result = (
            _apply_export_summary_to_result(
                export_result=export_result,
                export_summary=export_summary,
            )
        )

        st.session_state[
            "document_notion_result"
        ] = normalized_result

        if current_document_id:
            update_document_export_result(
                document_id=current_document_id,
                export_result=normalized_result,
            )

        progress_bar.progress(
            100,
            text=(
                "整份 Notion 詳細學習筆記"
                "處理完成。"
            ),
        )

        total_count = export_summary[
            "total_count"
        ]

        processed_count = export_summary[
            "processed_count"
        ]

        completed_count = export_summary[
            "completed_count"
        ]

        failed_count = export_summary[
            "failed_count"
        ]

        pending_count = export_summary[
            "pending_count"
        ]

        is_finished = export_summary[
            "is_finished"
        ]

        cached_visual_count = _safe_int(
            normalized_result.get(
                "cached_visual_count",
                0,
            )
        )

        cached_note_count = _safe_int(
            normalized_result.get(
                "cached_note_count",
                0,
            )
        )

        if is_finished:
            if processed_count > 0:
                st.success(
                    f"匯出完成：本次處理 "
                    f"{processed_count} 個 Module；"
                    f"共成功建立或確認 "
                    f"{completed_count} / "
                    f"{total_count} 個 Module 子頁面。"
                )
            else:
                st.success(
                    f"匯出完成：共成功建立或確認 "
                    f"{completed_count} / "
                    f"{total_count} 個 Module 子頁面。"
                )

        elif failed_count > 0:
            st.warning(
                f"本次處理 {processed_count} 個 Module；"
                f"目前成功 {completed_count} 個，"
                f"失敗 {failed_count} 個，"
                f"另有 {pending_count} 個尚未處理。"
            )

        elif pending_count > 0:
            st.info(
                f"本次處理 {processed_count} 個 Module；"
                f"目前成功 {completed_count} 個，"
                f"尚有 {pending_count} 個等待處理。"
            )

        else:
            st.info(
                "目前沒有需要執行的 Module。"
            )

        cache_col1, cache_col2 = st.columns(2)

        with cache_col1:
            st.markdown("**本次使用圖片分析快取**")
            st.metric(
                "圖片快取命中",
                f"{cached_visual_count} 個 Module",
                label_visibility="collapsed",
            )

        with cache_col2:
            st.markdown("**本次使用詳細筆記快取**")
            st.metric(
                "筆記快取命中",
                f"{cached_note_count} 個 Module",
                label_visibility="collapsed",
            )

        if cached_visual_count or cached_note_count:
            st.info(
                "已直接讀取快取資料，對應 Module "
                "不會重新進行 AI 分析。"
            )

    except Exception as error:
        progress_bar.empty()
        progress_status.empty()

        st.error(
            "整份 Notion 詳細學習筆記建立失敗："
            f"{error}"
        )


st.title("📝 AI Notion 筆記整理器")
st.caption(
    "上傳文件，自動整理成適合貼到 Notion "
    "的結構化筆記。"
)

if st.button("測試 AI 連線"):
    with st.spinner(
        "正在測試 OpenAI API 連線..."
    ):
        try:
            connection_result = (
                test_openai_connection()
            )

            st.success(connection_result)

        except Exception as error:
            st.error(
                f"AI 連線失敗：{error}"
            )

st.divider()
st.subheader("📤 上傳文件")

uploaded_file = st.file_uploader(
    "請選擇檔案",
    type=["pdf", "docx", "txt", "md"],
    help=(
        f"支援格式："
        f"{', '.join(SUPPORTED_FILE_TYPES)}"
    ),
)

if (
    uploaded_file is None
    and "parsed_document"
    not in st.session_state
):
    st.info(
        "請先上傳 PDF、DOCX、TXT 或 "
        "Markdown 檔案。"
    )

if uploaded_file is not None:
    if (
        "current_file_name"
        in st.session_state
        and st.session_state[
            "current_file_name"
        ]
        != uploaded_file.name
    ):
        clear_previous_result()

    file_size_mb = (
        uploaded_file.size / (1024 * 1024)
    )

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "檔案名稱",
        uploaded_file.name,
    )

    col2.metric(
        "檔案大小",
        f"{file_size_mb:.2f} MB",
    )

    col3.metric(
        "AI 模型",
        OPENAI_MODEL,
    )

    is_valid, error_message = validate_file(
        uploaded_file
    )

    if not is_valid:
        st.error(error_message)

    else:
        st.success("檔案驗證通過。")

        if st.button(
            "開始分析",
            type="primary",
        ):
            try:
                extension = Path(
                    uploaded_file.name
                ).suffix.lower()

                file_bytes = (
                    uploaded_file.getvalue()
                )

                parsed_document = (
                    parse_uploaded_file(
                        uploaded_file,
                        extension,
                    )
                )

                raw_text = parsed_document[
                    "raw_text"
                ]

                if not raw_text.strip():
                    st.warning(
                        "這份文件沒有可讀取的文字內容。"
                    )
                    st.stop()

                chapters = detect_chapters(
                    raw_text
                )

                cleaned_text = clean_text(
                    raw_text
                )

                chunks = chunk_text(
                    cleaned_text
                )

                if not chunks:
                    st.warning(
                        "文件清理後沒有可供分析的內容。"
                    )
                    st.stop()

                file_hash = create_file_hash(
                    file_bytes
                )

                database_document = (
                    create_or_update_document(
                        file_name=uploaded_file.name,
                        file_extension=extension,
                        file_size_bytes=(
                            uploaded_file.size
                        ),
                        file_hash=file_hash,
                        metadata=parsed_document[
                            "metadata"
                        ],
                        chapters=chapters,
                    )
                )

                st.session_state[
                    "current_file_name"
                ] = uploaded_file.name

                st.session_state[
                    "current_document_id"
                ] = database_document.id

                st.session_state[
                    "parsed_document"
                ] = parsed_document

                st.session_state[
                    "cleaned_text"
                ] = cleaned_text

                st.session_state[
                    "chapters"
                ] = chapters

                st.session_state[
                    "chunks"
                ] = chunks

                reset_keys = [
                    "chunk_result",
                    "final_result",
                    "all_chunk_results",
                    "notion_page_url",
                    "chapter_notes",
                    "selected_chapter_note_id",
                    "scroll_to_chapter_note",
                    "chapter_visual_contexts",
                    "document_notion_result",
                    "resume_export_estimate",
                ]

                for key in reset_keys:
                    st.session_state.pop(
                        key,
                        None,
                    )

                st.success(
                    "檔案解析、章節偵測與 SQLite "
                    "文件紀錄建立完成。"
                )

            except Exception as error:
                st.error(
                    f"文件處理失敗：{error}"
                )

if "parsed_document" in st.session_state:
    parsed_document = st.session_state[
        "parsed_document"
    ]

    metadata = parsed_document.get(
        "metadata",
        {},
    )

    cleaned_text = st.session_state[
        "cleaned_text"
    ]

    chapters = st.session_state.get(
        "chapters",
        [],
    )

    chunks = st.session_state[
        "chunks"
    ]

    current_file_name = (
        st.session_state.get(
            "current_file_name",
            metadata.get(
                "file_name",
                "未命名文件",
            ),
        )
    )

    st.divider()
    st.subheader("📄 文件解析結果")

    preview_col1, preview_col2, preview_col3 = (
        st.columns(3)
    )

    preview_col1.metric(
        "文字字數",
        metadata.get(
            "character_count",
            len(cleaned_text),
        ),
    )

    preview_col2.metric(
        "段落數量",
        metadata.get(
            "paragraph_count",
            0,
        ),
    )

    preview_col3.metric(
        "檔案格式",
        metadata.get(
            "file_extension",
            "",
        ),
    )

    if st.session_state.get(
        "current_document_id"
    ):
        st.caption(
            "SQLite 文件 ID："
            f"{st.session_state['current_document_id']}"
        )

    st.text_area(
        "清理後文字預覽",
        value=cleaned_text,
        height=300,
    )

    st.divider()
    st.subheader("📚 章節偵測結果")

    st.metric(
        "偵測到主章節數",
        len(chapters),
    )

    if "chapter_notes" not in st.session_state:
        st.session_state[
            "chapter_notes"
        ] = {}

    if (
        "chapter_visual_contexts"
        not in st.session_state
    ):
        st.session_state[
            "chapter_visual_contexts"
        ] = {}

    if chapters:
        for chapter_index, chapter in enumerate(
            chapters,
            start=1,
        ):
            chapter_id = (
                chapter.get("chapter_id")
                or chapter_index
            )

            subsection_count = len(
                chapter.get(
                    "subsections",
                    [],
                )
            )

            chapter_title = (
                f"第 {chapter_id} 章｜"
                f"{chapter.get('title', '未命名章節')}"
            )

            with st.expander(chapter_title):
                current_document_id = (
                    st.session_state.get(
                        "current_document_id"
                    )
                )

                learning_item_counts = {
                    "quiz_count": 0,
                    "flashcard_count": 0,
                }

                if current_document_id:
                    learning_item_counts = (
                        count_chapter_learning_items(
                            document_id=(
                                current_document_id
                            ),
                            source_chapter_id=str(
                                chapter_id
                            ),
                        )
                    )

                st.caption(
                    f"標題來源："
                    f"{chapter.get('source', '未知')}｜"
                    f"子章節數：{subsection_count}｜"
                    f"字元數："
                    f"{len(chapter.get('content', ''))}｜"
                    f"Quiz："
                    f"{learning_item_counts.get('quiz_count', 0)} 題｜"
                    f"Flash Cards："
                    f"{learning_item_counts.get('flashcard_count', 0)} 張"
                )

                st.text_area(
                    label=(
                        f"主章節內容預覽 "
                        f"{chapter_id}"
                    ),
                    value=chapter.get(
                        "content",
                        "",
                    )[:3000],
                    height=250,
                    key=(
                        f"chapter_preview_"
                        f"{chapter_id}"
                    ),
                )

                if st.button(
                    "生成詳細學習筆記",
                    key=(
                        f"generate_chapter_note_"
                        f"{chapter_id}"
                    ),
                ):
                    with st.spinner(
                        "AI 正在整理 "
                        f"{chapter.get('title', '此章節')}..."
                    ):
                        try:
                            visual_context = []

                            is_pdf = (
                                metadata.get(
                                    "file_extension"
                                )
                                == ".pdf"
                            )

                            has_pdf_data = bool(
                                parsed_document.get(
                                    "pdf_bytes"
                                )
                                and parsed_document.get(
                                    "page_texts"
                                )
                            )

                            if (
                                is_pdf
                                and has_pdf_data
                            ):
                                visual_context = (
                                    analyze_chapter_visuals(
                                        chapter=chapter,
                                        pdf_bytes=(
                                            parsed_document[
                                                "pdf_bytes"
                                            ]
                                        ),
                                        page_texts=(
                                            parsed_document[
                                                "page_texts"
                                            ]
                                        ),
                                        max_pages=3,
                                    )
                                )

                                st.session_state[
                                    "chapter_visual_contexts"
                                ][
                                    chapter_id
                                ] = visual_context

                            chapter_note = (
                                analyze_chapter(
                                    chapter=chapter,
                                    visual_context=(
                                        visual_context
                                    ),
                                )
                            )

                            current_document_id = (
                                st.session_state.get(
                                    "current_document_id"
                                )
                            )

                            if current_document_id:
                                save_result = (
                                    save_chapter_learning_items(
                                        document_id=(
                                            current_document_id
                                        ),
                                        source_chapter_id=str(
                                            chapter_id
                                        ),
                                        chapter_note=(
                                            chapter_note
                                        ),
                                    )
                                )

                                if save_result.get(
                                    "saved"
                                ):
                                    st.success(
                                        "已寫入 SQLite："
                                        f"{save_result.get('quiz_count', 0)} "
                                        "題 Quiz、"
                                        f"{save_result.get('flashcard_count', 0)} "
                                        "張 Flash Cards。"
                                    )
                                else:
                                    st.warning(
                                        "Quiz / Flash Cards "
                                        "未寫入 SQLite："
                                        f"{save_result.get('reason', '')}"
                                    )

                            st.session_state[
                                "chapter_notes"
                            ][
                                chapter_id
                            ] = chapter_note

                            st.session_state[
                                "selected_chapter_note_id"
                            ] = chapter_id

                            st.session_state[
                                "scroll_to_chapter_note"
                            ] = True

                            st.success(
                                "詳細學習筆記生成完成。"
                            )

                        except Exception as error:
                            st.error(
                                "章節學習筆記生成失敗："
                                f"{error}"
                            )

                if (
                    chapter_id
                    in st.session_state[
                        "chapter_notes"
                    ]
                ):
                    if st.button(
                        "查看這章詳細學習筆記",
                        key=(
                            f"view_chapter_note_"
                            f"{chapter_id}"
                        ),
                    ):
                        st.session_state[
                            "selected_chapter_note_id"
                        ] = chapter_id

                        st.session_state[
                            "scroll_to_chapter_note"
                        ] = True

                subsections = chapter.get(
                    "subsections",
                    [],
                )

                if subsections:
                    st.markdown("#### 子章節")

                    for subsection_index, subsection in enumerate(
                        subsections,
                        start=1,
                    ):
                        section_id = (
                            subsection.get(
                                "section_id"
                            )
                            or subsection_index
                        )

                        subsection_title = (
                            f"{subsection.get('title', '未命名子章節')}｜"
                            f"{len(subsection.get('content', ''))} 字元"
                        )

                        with st.expander(
                            subsection_title
                        ):
                            st.text_area(
                                label=(
                                    "子章節內容預覽 "
                                    f"{chapter_id}_"
                                    f"{section_id}"
                                ),
                                value=subsection.get(
                                    "content",
                                    "",
                                )[:2000],
                                height=180,
                                key=(
                                    "subsection_preview_"
                                    f"{chapter_id}_"
                                    f"{section_id}"
                                ),
                            )
                else:
                    st.info(
                        "此主章節未偵測到明確子章節。"
                    )

        selected_chapter_note_id = (
            st.session_state.get(
                "selected_chapter_note_id"
            )
        )

        chapter_notes = st.session_state.get(
            "chapter_notes",
            {},
        )

        if (
            selected_chapter_note_id
            in chapter_notes
        ):
            st.markdown(
                (
                    '<div id="'
                    'chapter-learning-note-detail'
                    '"></div>'
                ),
                unsafe_allow_html=True,
            )

            if st.session_state.get(
                "scroll_to_chapter_note"
            ):
                components.html(
                    """
                    <script>
                        setTimeout(function() {
                            const target =
                                window.parent.document
                                .getElementById(
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

                st.session_state[
                    "scroll_to_chapter_note"
                ] = False

            show_chapter_learning_note(
                chapter_notes[
                    selected_chapter_note_id
                ]
            )

    else:
        st.info(
            "未偵測到明確章節，系統將整份文件"
            "視為單一章節。"
        )

    st.divider()
    st.subheader("✂️ 文字分段預覽")

    st.metric(
        "分段總數",
        len(chunks),
    )

    for chunk in chunks:
        title = (
            f"第 {chunk.get('chunk_id', '?')} 段｜"
            f"{chunk.get('character_count', 0)} 字元"
        )

        with st.expander(title):
            st.text(
                chunk.get("content", "")
            )

    st.divider()
    st.subheader(
        "📚 整份文件分析與 Notion 匯出"
    )

    current_document_id = (
        st.session_state.get(
            "current_document_id"
        )
    )

    if current_document_id:
        document_learning_counts = (
            count_document_learning_items(
                current_document_id
            )
        )

        learning_col1, learning_col2 = (
            st.columns(2)
        )

        learning_col1.metric(
            "已儲存 Quiz",
            f"{document_learning_counts.get('quiz_count', 0)} 題",
        )

        learning_col2.metric(
            "已儲存 Flash Cards",
            f"{document_learning_counts.get('flashcard_count', 0)} 張",
        )

    show_export_estimates(
        document_name=current_file_name,
        chapters=chapters,
        parsed_document=parsed_document,
    )

    analysis_col, sync_col, resume_col, restart_col = (
        st.columns(4)
    )

    with analysis_col:
        if st.button(
            "分析整份文件",
            type="primary",
        ):
            with st.spinner(
                "AI 正在分析所有內容並整合筆記..."
            ):
                try:
                    final_result, chunk_results = (
                        analyze_document(chunks)
                    )

                    st.session_state[
                        "final_result"
                    ] = final_result

                    st.session_state[
                        "all_chunk_results"
                    ] = chunk_results

                    st.session_state.pop(
                        "notion_page_url",
                        None,
                    )

                    st.success(
                        "完整文件分析完成。"
                    )

                except Exception as error:
                    st.error(
                        f"完整文件分析失敗：{error}"
                    )

    with sync_col:
        if st.button(
            "從快取同步練習題",
            width="stretch",
        ):
            current_document_id = (
                st.session_state.get(
                    "current_document_id"
                )
            )

            with st.spinner(
                "正在從詳細筆記快取同步 Quiz 與 Flash Cards..."
            ):
                try:
                    sync_result = (
                        sync_document_learning_cache_to_sqlite(
                            document_name=current_file_name,
                            chapters=chapters,
                            document_id=current_document_id,
                        )
                    )

                    synced_chapters = int(
                        sync_result.get(
                            "synced_chapter_count",
                            0,
                        )
                        or 0
                    )

                    skipped_chapters = int(
                        sync_result.get(
                            "skipped_chapter_count",
                            0,
                        )
                        or 0
                    )

                    failed_chapters = int(
                        sync_result.get(
                            "failed_chapter_count",
                            0,
                        )
                        or 0
                    )

                    synced_quizzes = int(
                        sync_result.get(
                            "synced_quiz_count",
                            0,
                        )
                        or 0
                    )

                    synced_flashcards = int(
                        sync_result.get(
                            "synced_flashcard_count",
                            0,
                        )
                        or 0
                    )

                    if synced_chapters > 0:
                        st.success(
                            "SQLite 同步完成："
                            f"共回填 {synced_chapters} 個 Module、"
                            f"{synced_quizzes} 題 Quiz、"
                            f"{synced_flashcards} 張 Flash Cards。"
                        )

                    elif failed_chapters == 0:
                        st.info(
                            "沒有需要回填的資料。"
                            f"已有 {skipped_chapters} 個 Module "
                            "存在 SQLite 學習資料。"
                        )

                    if failed_chapters > 0:
                        st.warning(
                            f"有 {failed_chapters} 個 Module "
                            "同步失敗。"
                        )

                        for error_message in (
                            sync_result.get("errors", [])
                            or []
                        ):
                            st.error(str(error_message))

                    st.rerun()

                except Exception as error:
                    st.error(
                        "從快取同步 SQLite 失敗："
                        f"{error}"
                    )

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

    if (
        "document_notion_result"
        in st.session_state
    ):
        document_notion_result = (
            st.session_state[
                "document_notion_result"
            ]
        )

        parent_page_url = str(
            document_notion_result.get(
                "parent_page_url",
                "",
            )
            or document_notion_result.get(
                "notion_parent_url",
                "",
            )
        ).strip()

        if parent_page_url:
            st.link_button(
                "開啟 Notion 詳細學習筆記",
                parent_page_url,
            )

        result_col1, result_col2 = (
            st.columns(2)
        )

        result_col1.metric(
            "圖片分析快取",
            f"{document_notion_result.get('cached_visual_count', 0)} 個",
        )

        result_col2.metric(
            "詳細筆記快取",
            f"{document_notion_result.get('cached_note_count', 0)} 個",
        )

        failed_chapters = (
            _normalize_export_items(
                document_notion_result.get(
                    "failed_chapters"
                )
            )
        )

        if failed_chapters:
            with st.expander(
                "查看尚未完成章節"
            ):
                for failed_chapter in (
                    failed_chapters
                ):
                    _show_failed_export_chapter(
                        failed_chapter
                    )

    st.divider()
    st.subheader("🤖 單段分析測試")

    if st.button("分析第一段內容"):
        first_chunk = chunks[0]

        with st.spinner(
            "AI 正在分析第一段內容..."
        ):
            try:
                chunk_result = analyze_chunk(
                    chunk_content=first_chunk[
                        "content"
                    ],
                    chunk_id=first_chunk[
                        "chunk_id"
                    ],
                )

                st.session_state[
                    "chunk_result"
                ] = chunk_result

                st.success(
                    "第一段 AI 分析完成。"
                )

            except Exception as error:
                st.error(
                    f"AI 分析失敗：{error}"
                )


show_chunk_result()

if "parsed_document" in st.session_state:
    current_file_name = (
        st.session_state.get(
            "current_file_name",
            "未命名文件",
        )
    )

    show_final_result(
        current_file_name
    )
