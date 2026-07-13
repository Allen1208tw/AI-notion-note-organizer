import streamlit as st

from src.services.learning_database_service import (
    count_document_learning_items,
    delete_document_and_related_files,
    get_document_storage_usage,
    get_document_with_chapters,
    list_documents,
)


st.set_page_config(
    page_title="文件管理",
    page_icon="📂",
    layout="wide",
)


def inject_full_text_css() -> None:
    """
    讓 Streamlit 頁面中的文字盡量完整顯示，不用 ... 截斷。
    """

    st.markdown(
        """
        <style>
        /* 全站文字允許換行 */
        html, body, [class*="css"] {
            white-space: normal !important;
            overflow-wrap: anywhere !important;
            word-break: break-word !important;
        }

        /* Markdown / Caption / 一般文字 */
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

        /* Selectbox 顯示文字 */
        div[data-baseweb="select"] span,
        div[data-baseweb="select"] div,
        div[data-baseweb="popover"] span,
        div[data-baseweb="popover"] div {
            white-space: normal !important;
            overflow: visible !important;
            text-overflow: clip !important;
            overflow-wrap: anywhere !important;
            word-break: break-word !important;
            line-height: 1.4 !important;
        }

        /* Selectbox 高度允許變高 */
        div[data-baseweb="select"] > div {
            min-height: auto !important;
            height: auto !important;
            align-items: flex-start !important;
        }

        /* Selectbox 下拉選項允許換行 */
        li[role="option"] {
            white-space: normal !important;
            overflow: visible !important;
            text-overflow: clip !important;
            height: auto !important;
            min-height: 40px !important;
            align-items: flex-start !important;
            padding-top: 10px !important;
            padding-bottom: 10px !important;
        }

        /* Metric 不要截斷 */
        div[data-testid="stMetric"],
        div[data-testid="stMetric"] label,
        div[data-testid="stMetric"] div {
            white-space: normal !important;
            overflow: visible !important;
            text-overflow: clip !important;
            overflow-wrap: anywhere !important;
            word-break: break-word !important;
        }

        /* Button / Link button 不要截斷 */
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
            min-height: 38px !important;
        }

        /* Expander 標題不要截斷 */
        details summary,
        details summary span,
        div[data-testid="stExpander"] summary,
        div[data-testid="stExpander"] summary p {
            white-space: normal !important;
            overflow: visible !important;
            text-overflow: clip !important;
            overflow-wrap: anywhere !important;
            word-break: break-word !important;
            line-height: 1.45 !important;
        }

        /* Text input 內文字 */
        input,
        textarea {
            white-space: normal !important;
            overflow: visible !important;
            text-overflow: clip !important;
        }

        /* Code block 路徑允許換行，不要橫向撐爆 */
        pre,
        code {
            white-space: pre-wrap !important;
            overflow-wrap: anywhere !important;
            word-break: break-word !important;
        }

        /* 自訂狀態卡片完整顯示 */
        .full-text-card {
            border: 1px solid rgba(128,128,128,0.25);
            border-radius: 12px;
            padding: 14px 16px;
            margin-bottom: 10px;
            white-space: normal !important;
            overflow: visible !important;
            text-overflow: clip !important;
            overflow-wrap: anywhere !important;
            word-break: break-word !important;
        }

        .full-text-card-title {
            font-size: 0.9rem;
            opacity: 0.75;
            white-space: normal !important;
            overflow: visible !important;
            text-overflow: clip !important;
        }

        .full-text-card-status {
            font-size: 1.1rem;
            font-weight: 700;
            margin-top: 4px;
            white-space: normal !important;
            overflow: visible !important;
            text-overflow: clip !important;
        }

        .full-text-card-description {
            font-size: 0.88rem;
            opacity: 0.75;
            margin-top: 6px;
            white-space: normal !important;
            overflow: visible !important;
            text-overflow: clip !important;
            overflow-wrap: anywhere !important;
            word-break: break-word !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


inject_full_text_css()


def safe_getattr(obj, attr_name: str, default=None):
    """安全取得物件屬性，避免舊資料表欄位不存在時報錯。"""

    return getattr(obj, attr_name, default)

def format_file_size(size_bytes: int | float | None) -> str:
    """將 bytes 自動轉成 B / KB / MB / GB 顯示。"""

    if size_bytes is None:
        return "0 B"

    try:
        size_bytes = float(size_bytes)
    except (TypeError, ValueError):
        return "0 B"

    if size_bytes < 1024:
        return f"{size_bytes:.0f} B"

    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.2f} KB"

    if size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.2f} MB"

    return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"

def status_badge(status: str) -> str:
    """轉換狀態顯示。"""

    status_map = {
        "uploaded": "已上傳",
        "analyzed": "已完成文件解析",
        "exporting": "Notion 匯出中",
        "completed": "已完成",
        "failed": "處理失敗",
        "partial": "部分完成",
        "pending": "尚未處理",
        "skipped": "已跳過",
    }

    return status_map.get(status or "pending", status or "pending")


def show_status_card(
    title: str,
    status: str,
    description: str,
) -> None:
    """顯示完整狀態卡片，避免 st.metric 截斷文字。"""

    st.markdown(
        f"""
        <div class="full-text-card">
            <div class="full-text-card-title">
                {title}
            </div>
            <div class="full-text-card-status">
                {status_badge(status)}
            </div>
            <div class="full-text-card-description">
                {description}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def get_status_description(
    status_type: str,
    status: str,
) -> str:
    """取得狀態說明。"""

    if status_type == "document":
        return {
            "uploaded": "文件已上傳，但尚未完成解析。",
            "analyzed": "文件已完成解析，並寫入 SQLite。",
            "exporting": "文件目前正在匯出到 Notion。",
            "completed": "文件已完成主要處理流程。",
            "failed": "文件處理過程曾發生錯誤。",
            "partial": "文件部分章節已完成，仍有未完成項目。",
            "pending": "文件尚未開始處理，或舊資料表沒有狀態欄位。",
        }.get(status, "未知文件狀態。")

    if status_type == "export":
        return {
            "completed": "此項目已成功建立 Notion 頁面。",
            "failed": "此項目匯出失敗，可回主頁續跑。",
            "partial": "部分 Module 已匯出成功。",
            "exporting": "目前正在匯出。",
            "pending": "尚未匯出到 Notion，或舊資料表沒有匯出狀態欄位。",
        }.get(status, "未知匯出狀態。")

    if status_type == "visual":
        return {
            "completed": "已完成 PDF 圖片分析快取。",
            "failed": "PDF 圖片分析快取失敗。",
            "pending": "尚未建立 PDF 圖片分析快取。",
            "skipped": "非 PDF 或不需要圖片分析。",
        }.get(status, "未知圖片分析快取狀態。")

    if status_type == "note":
        return {
            "completed": "已完成詳細學習筆記快取。",
            "failed": "詳細學習筆記快取失敗。",
            "pending": "尚未建立詳細學習筆記快取。",
        }.get(status, "未知詳細筆記快取狀態。")

    return "未知狀態。"


def build_document_options(documents) -> dict:
    """
    建立文件選單。

    顯示時不顯示文件 ID。
    如果檔名重複，才補上更新時間避免選項名稱重複。
    """

    document_options = {}

    for document in documents:
        file_name = safe_getattr(document, "file_name", "未命名文件")
        updated_at = safe_getattr(document, "updated_at", "未知時間")

        label = file_name

        if label in document_options:
            label = f"{file_name}（更新時間：{updated_at}）"

        document_options[label] = document.id

    return document_options


def show_delete_section(document_id: int) -> None:
    """顯示刪除文件區塊。"""

    storage_usage = get_document_storage_usage(document_id)

    st.divider()
    st.subheader("🗑️ 刪除本機文件資料")

    if not storage_usage.get("found"):
        st.warning("找不到此文件的儲存資訊。")
        return

    st.warning(
        "這個操作會刪除本機 SQLite 中的文件、章節、Quiz、Flash Cards、"
        "練習紀錄，以及本機快取與匯出狀態檔。"
        "\n\n"
        "不會刪除 Notion 裡已經建立的頁面。"
    )

    size_col1, size_col2, size_col3, size_col4 = st.columns(4)

    size_col1.metric(
        "預估資料庫資料",
        storage_usage.get("database_size_text", "0 B"),
    )

    size_col2.metric(
        "章節快取",
        storage_usage.get("cache_size_text", "0 B"),
    )

    size_col3.metric(
        "匯出狀態檔",
        storage_usage.get("export_state_size_text", "0 B"),
    )

    size_col4.metric(
        "預估釋放空間",
        storage_usage.get("total_size_text", "0 B"),
    )

    with st.expander("查看會刪除的本機資料"):
        st.write(f"文件名稱：{storage_usage.get('file_name', '未知文件')}")
        st.write(f"Module 數：{storage_usage.get('chapter_count', 0)}")
        st.write(f"Quiz 數：{storage_usage.get('quiz_count', 0)}")
        st.write(f"Flash Cards 數：{storage_usage.get('flashcard_count', 0)}")

        cache_dir = storage_usage.get("cache_dir", "")

        if cache_dir:
            st.write("章節快取資料夾：")
            st.code(cache_dir, language="text")

    delete_cache = st.checkbox(
        "同時刪除章節快取 outputs/chapter_cache",
        value=True,
    )

    delete_export_state = st.checkbox(
        "同時刪除匯出狀態 outputs/export_jobs",
        value=True,
    )

    confirm_text = st.text_input(
        "若確定要刪除，請輸入 DELETE",
        placeholder="DELETE",
    )

    delete_button_disabled = confirm_text != "DELETE"

    if st.button(
        "永久刪除此文件的本機資料",
        type="primary",
        disabled=delete_button_disabled,
    ):
        result = delete_document_and_related_files(
            document_id=document_id,
            delete_cache=delete_cache,
            delete_export_state=delete_export_state,
        )

        if result["deleted"]:
            st.success(
                f"已刪除本機文件資料：{result['file_name']}"
            )

            if result["deleted_dirs"]:
                st.write("已刪除資料夾：")

                for deleted_dir in result["deleted_dirs"]:
                    st.code(deleted_dir, language="text")

            if result["deleted_files"]:
                st.write("已刪除檔案：")

                for deleted_file in result["deleted_files"]:
                    st.code(deleted_file, language="text")

            st.info("頁面即將重新整理。")
            st.rerun()

        else:
            st.error(f"刪除失敗：{result['reason']}")


st.title("📂 文件管理")
st.caption("查看已分析文件、Module 狀態、學習資料與本機儲存空間。")

documents = list_documents()

if not documents:
    st.info("目前 SQLite 中還沒有任何文件紀錄。")
    st.stop()

document_options = build_document_options(documents)

selected_document_label = st.selectbox(
    "選擇文件",
    options=list(document_options.keys()),
)

selected_document_id = document_options[selected_document_label]

document = get_document_with_chapters(selected_document_id)

if document is None:
    st.error("找不到選擇的文件。")
    st.stop()

document_status = safe_getattr(document, "status", "pending")
document_export_status = safe_getattr(document, "export_status", "pending")
document_file_size = safe_getattr(document, "file_size_bytes", 0) or 0
document_file_extension = safe_getattr(document, "file_extension", "未知")
document_chapters = safe_getattr(document, "chapters", []) or []
document_file_name = safe_getattr(document, "file_name", "未命名文件")

st.divider()
st.subheader("📄 文件資訊")

info_col1, info_col2, info_col3, info_col4 = st.columns(4)

info_col1.metric("文件 ID", document.id)
info_col2.metric("檔案格式", document_file_extension)
info_col3.metric("檔案大小", format_file_size(document_file_size))
info_col4.metric("Module 數", len(document_chapters))

status_col1, status_col2 = st.columns(2)

with status_col1:
    show_status_card(
        title="文件狀態",
        status=document_status,
        description=get_status_description("document", document_status),
    )

with status_col2:
    show_status_card(
        title="Notion 匯出狀態",
        status=document_export_status,
        description=get_status_description("export", document_export_status),
    )

learning_counts = count_document_learning_items(document.id)

learn_col1, learn_col2 = st.columns(2)

learn_col1.metric(
    "已儲存 Quiz",
    f"{learning_counts['quiz_count']} 題",
)

learn_col2.metric(
    "已儲存 Flash Cards",
    f"{learning_counts['flashcard_count']} 張",
)

st.write(f"文件名稱：**{document_file_name}**")
st.write(f"建立時間：{safe_getattr(document, 'created_at', '未知')}")
st.write(f"更新時間：{safe_getattr(document, 'updated_at', '未知')}")

document_notion_page_url = safe_getattr(document, "notion_page_url", None)

if document_notion_page_url:
    st.link_button(
        "開啟 Notion 文件頁面",
        document_notion_page_url,
    )

st.divider()
st.subheader("📚 Module 清單")

if not document_chapters:
    st.info("此文件沒有章節紀錄。")

else:
    for chapter in document_chapters:
        source_chapter_id = safe_getattr(
            chapter,
            "source_chapter_id",
            safe_getattr(chapter, "chapter_id", ""),
        )

        chapter_title = safe_getattr(chapter, "title", "未命名 Module")

        title = (
            f"Module {source_chapter_id}｜"
            f"{chapter_title}"
        )

        with st.expander(title):
            chapter_export_status = safe_getattr(
                chapter,
                "export_status",
                "pending",
            )

            chapter_visual_cache_status = safe_getattr(
                chapter,
                "visual_cache_status",
                "pending",
            )

            chapter_note_cache_status = safe_getattr(
                chapter,
                "note_cache_status",
                "pending",
            )

            chapter_col1, chapter_col2, chapter_col3 = st.columns(3)

            with chapter_col1:
                show_status_card(
                    title="匯出狀態",
                    status=chapter_export_status,
                    description=get_status_description(
                        "export",
                        chapter_export_status,
                    ),
                )

            with chapter_col2:
                show_status_card(
                    title="圖片分析快取",
                    status=chapter_visual_cache_status,
                    description=get_status_description(
                        "visual",
                        chapter_visual_cache_status,
                    ),
                )

            with chapter_col3:
                show_status_card(
                    title="詳細筆記快取",
                    status=chapter_note_cache_status,
                    description=get_status_description(
                        "note",
                        chapter_note_cache_status,
                    ),
                )

            detail_col1, detail_col2, detail_col3 = st.columns(3)

            detail_col1.metric(
                "字元數",
                safe_getattr(chapter, "character_count", 0) or 0,
            )

            detail_col2.metric(
                "子章節數",
                safe_getattr(chapter, "subsection_count", 0) or 0,
            )

            detail_col3.metric(
                "資料來源",
                safe_getattr(chapter, "source", "未知") or "未知",
            )

            chapter_notion_page_url = safe_getattr(
                chapter,
                "notion_page_url",
                None,
            )

            if chapter_notion_page_url:
                st.link_button(
                    "開啟此 Module 的 Notion 子頁",
                    chapter_notion_page_url,
                )

show_delete_section(document.id)