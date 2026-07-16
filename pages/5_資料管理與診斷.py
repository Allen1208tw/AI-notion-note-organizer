from __future__ import annotations

from datetime import datetime

import pandas as pd
import streamlit as st

from src.services.learning_data_admin_service import (
    deduplicate_document_learning_items,
    delete_document_learning_data,
    delete_single_chapter_learning_data,
    get_all_learning_documents,
    get_document_diagnostics,
)
from src.services.chapter_notion_service import (
    sync_single_chapter_cache_to_sqlite,
)


st.set_page_config(
    page_title="資料管理",
    page_icon="🛠️",
    layout="wide",
)


def inject_page_css() -> None:
    """設定資料管理頁面樣式。"""

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

        button,
        button div,
        button p {
            white-space: normal !important;
            overflow: visible !important;
            text-overflow: clip !important;
            overflow-wrap: anywhere !important;
            word-break: break-word !important;
            height: auto !important;
        }

        .diagnostic-card {
            border: 1px solid rgba(128, 128, 128, 0.24);
            border-radius: 16px;
            padding: 18px;
            margin-bottom: 14px;
            background: rgba(127, 127, 127, 0.04);
        }

        .diagnostic-title {
            font-size: 1.05rem;
            font-weight: 700;
            margin-bottom: 6px;
        }

        .diagnostic-subtitle {
            font-size: 0.92rem;
            opacity: 0.72;
            line-height: 1.5;
        }

        .healthy-text {
            color: #2e8b57;
            font-weight: 700;
        }

        .warning-text {
            color: #d97706;
            font-weight: 700;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


inject_page_css()


def safe_text(value, default: str = "") -> str:
    """安全轉換為字串。"""

    if value is None:
        return default

    try:
        return str(value)
    except Exception:
        return default


def safe_int(value, default: int = 0) -> int:
    """安全轉換為整數。"""

    try:
        if value is None:
            return default

        return int(value)
    except (TypeError, ValueError):
        return default


def format_datetime(value) -> str:
    """格式化日期時間。"""

    if value is None:
        return "未知時間"

    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")

    return safe_text(value, "未知時間")


def build_document_labels(
    documents: list[dict],
) -> list[str]:
    """建立文件選單標籤。"""

    name_counts: dict[str, int] = {}

    for document in documents:
        file_name = safe_text(
            document.get("file_name"),
            "未命名文件",
        )

        name_counts[file_name] = (
            name_counts.get(file_name, 0) + 1
        )

    labels = []

    for document in documents:
        file_name = safe_text(
            document.get("file_name"),
            "未命名文件",
        )

        if name_counts.get(file_name, 0) > 1:
            labels.append(
                (
                    f"{file_name}｜"
                    f"{format_datetime(document.get('updated_at'))}"
                )
            )
        else:
            labels.append(file_name)

    return labels


def show_document_summary(
    document: dict,
) -> None:
    """顯示文件總體統計。"""

    row1_col1, row1_col2, row1_col3, row1_col4 = (
        st.columns(4)
    )

    row1_col1.metric(
        "章節數",
        safe_int(
            document.get("chapter_count")
        ),
    )

    row1_col2.metric(
        "Quiz",
        safe_int(
            document.get("quiz_count")
        ),
    )

    row1_col3.metric(
        "Flash Cards",
        safe_int(
            document.get("flashcard_count")
        ),
    )

    row1_col4.metric(
        "弱點",
        safe_int(
            document.get("weak_point_count")
        ),
    )

    row2_col1, row2_col2, row2_col3, row2_col4 = (
        st.columns(4)
    )

    row2_col1.metric(
        "Quiz 作答",
        safe_int(
            document.get(
                "quiz_attempt_count"
            )
        ),
    )

    row2_col2.metric(
        "Flash Card 複習",
        safe_int(
            document.get(
                "flashcard_review_count"
            )
        ),
    )

    row2_col3.metric(
        "文件狀態",
        safe_text(
            document.get("status"),
            "unknown",
        ),
    )

    row2_col4.metric(
        "Notion 狀態",
        safe_text(
            document.get(
                "export_status"
            ),
            "pending",
        ),
    )


def show_diagnostic_summary(
    diagnostic: dict,
) -> None:
    """顯示診斷摘要。"""

    summary = diagnostic.get(
        "summary",
        {},
    )

    is_healthy = bool(
        diagnostic.get("is_healthy")
    )

    status_class = (
        "healthy-text"
        if is_healthy
        else "warning-text"
    )

    status_text = (
        "資料結構正常"
        if is_healthy
        else "偵測到需要注意的資料問題"
    )

    st.markdown(
        (
            '<div class="diagnostic-card">'
            '<div class="diagnostic-title">'
            'SQLite 資料健康狀態'
            '</div>'
            f'<div class="{status_class}">'
            f'{status_text}'
            '</div>'
            '<div class="diagnostic-subtitle">'
            f'檢查時間：'
            f'{format_datetime(diagnostic.get("checked_at"))}'
            '</div>'
            '</div>'
        ),
        unsafe_allow_html=True,
    )

    col1, col2, col3, col4 = st.columns(4)

    col1.metric(
        "有學習資料的章節",
        safe_int(
            summary.get(
                "chapter_with_learning_data_count"
            )
        ),
    )

    col2.metric(
        "重複章節來源 ID",
        safe_int(
            summary.get(
                "duplicate_source_id_count"
            )
        ),
    )

    col3.metric(
        "孤兒 Quiz 作答",
        safe_int(
            summary.get(
                "orphan_quiz_attempt_count"
            )
        ),
    )

    col4.metric(
        "孤兒 Flash Card 複習",
        safe_int(
            summary.get(
                "orphan_flashcard_review_count"
            )
        ),
    )

    col5, col6 = st.columns(2)

    col5.metric(
        "重複 Quiz",
        safe_int(summary.get("duplicate_quiz_count")),
    )

    col6.metric(
        "重複 Flash Cards",
        safe_int(summary.get("duplicate_flashcard_count")),
    )


def show_diagnostic_warnings(
    warnings: list[str],
) -> None:
    """顯示診斷警告。"""

    if not warnings:
        st.success(
            "目前沒有偵測到資料結構警告。"
        )
        return

    for warning in warnings:
        st.warning(warning)


def show_chapter_distribution(
    chapters: list[dict],
) -> None:
    """顯示每章 Quiz 與 Flash Card 分布。"""

    if not chapters:
        st.info(
            "目前沒有章節資料。"
        )
        return

    rows = []

    for chapter in chapters:
        rows.append(
            {
                "章節順序": chapter.get(
                    "chapter_order"
                ),
                "來源章節 ID": safe_text(
                    chapter.get(
                        "source_chapter_id"
                    )
                ),
                "章節標題": safe_text(
                    chapter.get("title"),
                    "未命名章節",
                ),
                "Quiz 數": safe_int(
                    chapter.get(
                        "quiz_count"
                    )
                ),
                "Flash Card 數": safe_int(
                    chapter.get(
                        "flashcard_count"
                    )
                ),
                "更新時間": format_datetime(
                    chapter.get(
                        "updated_at"
                    )
                ),
            }
        )

    dataframe = pd.DataFrame(rows)

    st.dataframe(
        dataframe,
        width="stretch",
        hide_index=True,
    )

    chart_data = dataframe[
        [
            "章節標題",
            "Quiz 數",
            "Flash Card 數",
        ]
    ].copy()

    if not chart_data.empty:
        chart_data = chart_data.set_index(
            "章節標題"
        )

        st.bar_chart(
            chart_data,
            width="stretch",
        )


def show_duplicate_cleanup(
    document_id: str,
) -> None:
    """Preview and safely merge duplicate Quiz and Flash Cards."""

    try:
        preview = deduplicate_document_learning_items(
            document_id=document_id,
            preview_only=True,
        )
    except Exception as error:
        st.error(f"讀取重複資料失敗：{error}")
        return

    duplicate_quizzes = safe_int(preview.get("duplicate_quiz_count"))
    duplicate_flashcards = safe_int(
        preview.get("duplicate_flashcard_count")
    )

    if duplicate_quizzes == 0 and duplicate_flashcards == 0:
        st.success("目前沒有重複的 Quiz 或 Flash Cards。")
        return

    metric_col1, metric_col2 = st.columns(2)
    metric_col1.metric("可合併的重複 Quiz", duplicate_quizzes)
    metric_col2.metric("可合併的重複 Flash Cards", duplicate_flashcards)

    st.info(
        "整理時會保留一份原始題目或卡片，並把作答紀錄、"
        "複習紀錄、弱點與排程移到保留項目，不會重新呼叫 AI。"
    )

    confirm_text = st.text_input(
        "輸入 MERGE DUPLICATES 進行確認",
        key=f"confirm_merge_duplicates_{document_id}",
    )

    if st.button(
        "安全合併重複資料",
        key=f"merge_duplicates_{document_id}",
        type="primary",
        disabled=confirm_text.strip() != "MERGE DUPLICATES",
        width="stretch",
    ):
        try:
            result = deduplicate_document_learning_items(
                document_id=document_id,
                preview_only=False,
            )
            st.session_state["deduplicate_success"] = result
            st.rerun()
        except Exception as error:
            st.error(f"合併重複資料失敗：{error}")


def show_single_chapter_cleanup(
    document_id: str,
    chapters: list[dict],
) -> None:
    """提供單一章節學習資料清除。"""

    if not chapters:
        st.info(
            "目前沒有可清除的章節。"
        )
        return

    chapter_labels = [
        (
            f"Module {chapter.get('chapter_order', '?')}｜"
            f"{safe_text(chapter.get('title'), '未命名章節')}｜"
            f"Quiz {safe_int(chapter.get('quiz_count'))}｜"
            f"Flash Cards {safe_int(chapter.get('flashcard_count'))}"
        )
        for chapter in chapters
    ]

    selected_index = st.selectbox(
        "選擇要清除的章節",
        options=list(
            range(len(chapters))
        ),
        format_func=lambda index: (
            chapter_labels[index]
        ),
        key=f"admin_chapter_selector_{document_id}",
    )

    selected_chapter = chapters[
        selected_index
    ]

    selected_chapter_id = safe_text(
        selected_chapter.get("id")
    )

    st.warning(
        "這個操作會刪除該章的 Quiz、Flash Cards、"
        "作答紀錄、複習紀錄與弱點資料。"
        "章節主紀錄會保留，之後可以重新同步快取。"
    )

    confirm_text = st.text_input(
        "輸入 DELETE CHAPTER 進行確認",
        key=(
            f"confirm_delete_chapter_"
            f"{document_id}_"
            f"{selected_chapter_id}"
        ),
    )

    delete_enabled = (
        confirm_text.strip()
        == "DELETE CHAPTER"
    )

    if st.button(
        "清除這個章節的學習資料",
        key=(
            f"delete_chapter_button_"
            f"{document_id}_"
            f"{selected_chapter_id}"
        ),
        type="primary",
        disabled=not delete_enabled,
        width="stretch",
    ):
        try:
            result = (
                delete_single_chapter_learning_data(
                    document_id=document_id,
                    chapter_id=selected_chapter_id,
                )
            )

            counts = result.get(
                "deleted_counts",
                {},
            )

            st.success(
                "章節學習資料已清除。"
                f"Quiz：{safe_int(counts.get('quizzes'))}、"
                f"Flash Cards：{safe_int(counts.get('flashcards'))}、"
                f"Quiz 作答：{safe_int(counts.get('quiz_attempts'))}、"
                f"Flash Card 複習："
                f"{safe_int(counts.get('flashcard_reviews'))}。"
            )

            st.rerun()

        except Exception as error:
            st.error(
                f"清除章節資料失敗：{error}"
            )



def show_single_chapter_resync(
    document_id: str,
    document_name: str,
    chapters: list[dict],
) -> None:
    """從詳細筆記快取重新同步單一章節。"""

    if not chapters:
        st.info(
            "目前沒有可同步的章節。"
        )
        return

    chapter_labels = [
        (
            f"Module {chapter.get('chapter_order', '?')}｜"
            f"{safe_text(chapter.get('title'), '未命名章節')}｜"
            f"Quiz {safe_int(chapter.get('quiz_count'))}｜"
            f"Flash Cards {safe_int(chapter.get('flashcard_count'))}"
        )
        for chapter in chapters
    ]

    selected_index = st.selectbox(
        "選擇要重新同步的章節",
        options=list(
            range(len(chapters))
        ),
        format_func=lambda index: (
            chapter_labels[index]
        ),
        key=(
            f"admin_resync_chapter_selector_"
            f"{document_id}"
        ),
    )

    selected_chapter = chapters[
        selected_index
    ]

    source_chapter_id = safe_text(
        selected_chapter.get(
            "source_chapter_id"
        )
        or selected_chapter.get(
            "chapter_order"
        )
    )

    chapter_title = safe_text(
        selected_chapter.get("title"),
        f"Module {source_chapter_id}",
    )

    quiz_count = safe_int(
        selected_chapter.get(
            "quiz_count"
        )
    )

    flashcard_count = safe_int(
        selected_chapter.get(
            "flashcard_count"
        )
    )

    st.markdown(
        (
            "**快取定位資訊**  \n"
            f"- 文件：`{document_name}`  \n"
            f"- source_chapter_id："
            f"`{source_chapter_id}`  \n"
            f"- 章節標題：`{chapter_title}`"
        )
    )

    if quiz_count == 0 and flashcard_count == 0:
        st.info(
            "該章目前沒有 Quiz 與 Flash Cards，"
            "可以安全地從詳細筆記快取重新同步。"
            "這個操作不會呼叫 AI，也不會修改 Notion。"
        )
    else:
        st.info(
            "該章已有學習資料；同步時會保留作答與複習紀錄，"
            "略過重複內容，只補上快取中缺少的 Quiz 或 Flash Cards。"
        )

    if st.button(
        "從快取重新同步這個章節",
        key=(
            f"resync_chapter_button_"
            f"{document_id}_"
            f"{source_chapter_id}"
        ),
        type="primary",
        width="stretch",
    ):
        try:
            result = (
                sync_single_chapter_cache_to_sqlite(
                    document_name=document_name,
                    document_id=document_id,
                    source_chapter_id=(
                        source_chapter_id
                    ),
                    chapter_title=chapter_title,
                )
            )

            if result.get("synced"):
                st.session_state[
                    "chapter_resync_success"
                ] = {
                    "document_name": (
                        document_name
                    ),
                    "chapter_title": (
                        chapter_title
                    ),
                    "quiz_count": (
                        safe_int(
                            result.get(
                                "quiz_count"
                            )
                        )
                    ),
                    "flashcard_count": (
                        safe_int(
                            result.get(
                                "flashcard_count"
                            )
                        )
                    ),
                    "added_quiz_count": safe_int(
                        result.get("added_quiz_count")
                    ),
                    "added_flashcard_count": safe_int(
                        result.get("added_flashcard_count")
                    ),
                    "skipped_quiz_count": safe_int(
                        result.get("skipped_quiz_count")
                    ),
                    "skipped_flashcard_count": safe_int(
                        result.get("skipped_flashcard_count")
                    ),
                }

                st.rerun()

            elif result.get("skipped"):
                st.warning(
                    safe_text(
                        result.get("reason"),
                        "章節同步已跳過。",
                    )
                )

            else:
                st.error(
                    "章節快取同步失敗："
                    f"{safe_text(result.get('reason'))}"
                )

        except Exception as error:
            st.error(
                f"章節快取同步失敗：{error}"
            )


def show_document_cleanup(
    document_id: str,
    document_name: str,
) -> None:
    """提供整份文件資料清除。"""

    delete_record = st.checkbox(
        "同時刪除 documents 主紀錄",
        value=False,
        key=(
            f"delete_document_record_"
            f"{document_id}"
        ),
    )

    if delete_record:
        st.error(
            "將同時刪除文件主紀錄。"
            "之後重新上傳時會建立新的文件 ID。"
        )
    else:
        st.warning(
            "將保留文件主紀錄，但清除全部章節、Quiz、"
            "Flash Cards、作答、複習與弱點資料。"
        )

    confirmation_target = (
        "DELETE DOCUMENT"
        if delete_record
        else "CLEAR LEARNING DATA"
    )

    confirm_text = st.text_input(
        (
            f"輸入 {confirmation_target} "
            "進行確認"
        ),
        key=(
            f"confirm_delete_document_"
            f"{document_id}"
        ),
    )

    delete_enabled = (
        confirm_text.strip()
        == confirmation_target
    )

    if st.button(
        (
            "刪除整份文件紀錄"
            if delete_record
            else "清除整份文件的學習資料"
        ),
        key=(
            f"delete_document_button_"
            f"{document_id}"
        ),
        type="primary",
        disabled=not delete_enabled,
        width="stretch",
    ):
        try:
            result = delete_document_learning_data(
                document_id=document_id,
                delete_document_record=delete_record,
            )

            counts = result.get(
                "deleted_counts",
                {},
            )

            st.success(
                f"{document_name} 的資料已清除。"
                f"章節：{safe_int(counts.get('chapters'))}、"
                f"Quiz：{safe_int(counts.get('quizzes'))}、"
                f"Flash Cards：{safe_int(counts.get('flashcards'))}、"
                f"弱點：{safe_int(counts.get('weak_points'))}。"
            )

            st.rerun()

        except Exception as error:
            st.error(
                f"清除文件資料失敗：{error}"
            )



def show_deduplicate_success_dialog() -> None:
    """Show the result after duplicate learning items are merged."""

    result = st.session_state.get("deduplicate_success")

    if not result:
        return

    @st.dialog("重複資料整理完成")
    def _dialog() -> None:
        st.success("重複資料已安全合併，相關學習紀錄已保留。")
        col1, col2 = st.columns(2)
        col1.metric(
            "已合併 Quiz",
            safe_int(result.get("merged_quiz_count")),
        )
        col2.metric(
            "已合併 Flash Cards",
            safe_int(result.get("merged_flashcard_count")),
        )
        st.caption(
            "作答、複習、弱點與排程已重新連到保留的項目。"
        )

        if st.button(
            "關閉",
            key="close_deduplicate_dialog",
            type="primary",
            width="stretch",
        ):
            st.session_state.pop("deduplicate_success", None)
            st.rerun()

    _dialog()


def show_resync_success_dialog() -> None:
    """顯示單章快取同步成功對話框。"""

    result = st.session_state.get(
        "chapter_resync_success"
    )

    if not result:
        return

    @st.dialog("✅ 章節同步成功")
    def _dialog() -> None:
        st.success(
            "已成功從詳細筆記快取重新寫入 SQLite。"
        )

        st.write(
            f"**文件：** "
            f"{safe_text(result.get('document_name'))}"
        )

        st.write(
            f"**章節：** "
            f"{safe_text(result.get('chapter_title'))}"
        )

        metric_col1, metric_col2 = st.columns(2)

        metric_col1.metric(
            "Quiz",
            safe_int(
                result.get("quiz_count")
            ),
        )

        metric_col2.metric(
            "Flash Cards",
            safe_int(
                result.get("flashcard_count")
            ),
        )

        added_col1, added_col2 = st.columns(2)
        added_col1.metric(
            "本次新增 Quiz",
            safe_int(result.get("added_quiz_count")),
        )
        added_col2.metric(
            "本次新增 Flash Cards",
            safe_int(result.get("added_flashcard_count")),
        )

        st.caption(
            "這次同步只讀取既有快取，"
            "沒有重新呼叫 AI，也沒有修改 Notion。"
        )

        if st.button(
            "關閉",
            key="close_chapter_resync_dialog",
            type="primary",
            width="stretch",
        ):
            st.session_state.pop(
                "chapter_resync_success",
                None,
            )

            st.rerun()

    _dialog()


st.title("🛠️ 資料管理與診斷")
st.caption(
    "檢查 SQLite 學習資料完整性，"
    "並管理文件或單一章節的學習資料。"
)


show_resync_success_dialog()
show_deduplicate_success_dialog()

try:
    documents = get_all_learning_documents()
except Exception as error:
    st.error(
        f"讀取 SQLite 文件失敗：{error}"
    )
    st.stop()

if not documents:
    st.info(
        "SQLite 目前沒有文件資料。"
    )
    st.stop()

document_labels = build_document_labels(
    documents
)

selected_document_index = st.selectbox(
    "選擇文件",
    options=list(
        range(len(documents))
    ),
    format_func=lambda index: (
        document_labels[index]
    ),
    key="admin_document_selector",
)

selected_document = documents[
    selected_document_index
]

selected_document_id = safe_text(
    selected_document.get("id")
)

selected_document_name = safe_text(
    selected_document.get("file_name"),
    "未命名文件",
)

st.markdown(
    (
        '<div class="diagnostic-card">'
        '<div class="diagnostic-title">'
        f'{selected_document_name}'
        '</div>'
        '<div class="diagnostic-subtitle">'
        f'文件 ID：{selected_document_id}｜'
        f'更新時間：'
        f'{format_datetime(selected_document.get("updated_at"))}'
        '</div>'
        '</div>'
    ),
    unsafe_allow_html=True,
)

show_document_summary(
    selected_document
)

try:
    diagnostic = get_document_diagnostics(
        selected_document_id
    )
except Exception as error:
    st.error(
        f"執行資料診斷失敗：{error}"
    )
    st.stop()

tab_diagnostic, tab_chapters, tab_cleanup = (
    st.tabs(
        [
            "資料診斷",
            "章節資料分布",
            "清除與重建",
        ]
    )
)

with tab_diagnostic:
    show_diagnostic_summary(
        diagnostic
    )

    st.subheader("診斷警告")

    show_diagnostic_warnings(
        diagnostic.get(
            "warnings",
            [],
        )
    )

with tab_chapters:
    st.subheader(
        "每章 Quiz／Flash Card 分布"
    )

    show_chapter_distribution(
        diagnostic.get(
            "chapters",
            [],
        )
    )

with tab_cleanup:
    st.subheader("重複資料安全整理")

    show_duplicate_cleanup(
        document_id=selected_document_id,
    )

    st.divider()

    st.subheader("單一章節重新同步")

    show_single_chapter_resync(
        document_id=selected_document_id,
        document_name=selected_document_name,
        chapters=diagnostic.get(
            "chapters",
            [],
        ),
    )

    st.divider()

    st.subheader("單一章節清除")

    show_single_chapter_cleanup(
        document_id=selected_document_id,
        chapters=diagnostic.get(
            "chapters",
            [],
        ),
    )

    st.divider()

    st.subheader("整份文件清除")

    show_document_cleanup(
        document_id=selected_document_id,
        document_name=selected_document_name,
    )
