from __future__ import annotations

import streamlit as st

from src.services.learning_database_service import (
    get_document_with_chapters,
    list_documents,
)


st.set_page_config(
    page_title="文件管理｜AI Notion 筆記整理器",
    page_icon="📚",
    layout="wide",
)


def format_file_size(file_size_bytes: int) -> str:
    """將檔案大小轉成容易閱讀的格式。"""

    if file_size_bytes < 1024:
        return f"{file_size_bytes} B"

    if file_size_bytes < 1024 * 1024:
        return f"{file_size_bytes / 1024:.1f} KB"

    return f"{file_size_bytes / (1024 * 1024):.2f} MB"


def format_datetime(value) -> str:
    """格式化資料庫時間。"""

    if not value:
        return "尚無資料"

    return value.strftime("%Y-%m-%d %H:%M")


def status_label(status: str) -> str:
    """將內部狀態轉成中文顯示文字。"""

    status_map = {
        "uploaded": "已上傳",
        "analyzed": "已完成文件解析",
        "exporting": "Notion 匯出中",
        "completed": "已完成",
        "failed": "處理失敗",
        "pending": "尚未處理",
        "skipped": "已跳過",
    }

    return status_map.get(status, status or "尚無狀態")


def status_description(
    status: str,
    status_type: str,
) -> str:
    """依不同狀態類型顯示完整說明。"""

    normalized_status = status or "pending"

    descriptions = {
        "export": {
            "pending": "尚未匯出到 Notion。",
            "exporting": "目前正在建立 Notion 頁面。",
            "completed": "此 Module 已成功建立 Notion 子頁面。",
            "failed": "此 Module 匯出到 Notion 時發生錯誤。",
            "skipped": "此 Module 本次被略過。",
        },
        "visual_cache": {
            "pending": "尚未建立 PDF 圖片分析快取。",
            "exporting": "正在分析 PDF 圖片或頁面畫面。",
            "completed": "已完成 PDF 圖片分析快取。",
            "failed": "PDF 圖片分析快取建立失敗。",
            "skipped": "此章節未使用圖片分析。",
        },
        "note_cache": {
            "pending": "尚未建立詳細學習筆記快取。",
            "exporting": "正在生成詳細學習筆記。",
            "completed": "已完成詳細學習筆記快取。",
            "failed": "詳細學習筆記快取建立失敗。",
            "skipped": "此章節未建立詳細筆記快取。",
        },
    }

    return descriptions.get(status_type, {}).get(
        normalized_status,
        "尚無完整狀態說明。",
    )


def status_badge(status: str) -> str:
    """產生狀態符號。"""

    badge_map = {
        "pending": "⚪",
        "uploaded": "📄",
        "analyzed": "🔍",
        "exporting": "🟡",
        "completed": "🟢",
        "failed": "🔴",
        "skipped": "⚫",
    }

    return badge_map.get(status or "pending", "⚪")


def show_status_card(
    title: str,
    status: str,
    status_type: str,
) -> None:
    """顯示完整狀態卡片，避免 st.metric 文字被截斷。"""

    label = status_label(status)
    description = status_description(
        status=status,
        status_type=status_type,
    )

    st.markdown(
        f"""
        <div style="
            border: 1px solid rgba(128, 128, 128, 0.25);
            border-radius: 10px;
            padding: 12px 14px;
            margin-bottom: 8px;
            min-height: 120px;
        ">
            <div style="font-size: 0.9rem; opacity: 0.75;">
                {title}
            </div>
            <div style="font-size: 1.05rem; font-weight: 700; margin-top: 6px;">
                {status_badge(status)} {label}
            </div>
            <div style="font-size: 0.85rem; opacity: 0.8; margin-top: 8px; line-height: 1.45;">
                {description}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


st.title("📚 文件管理")
st.caption("查看已分析的文件、Module 與處理狀態。")

documents = list_documents()

if not documents:
    st.info(
        "目前還沒有文件紀錄。請回到首頁上傳文件並按下「開始分析」。"
    )
    st.stop()

total_documents = len(documents)

total_chapters = sum(
    len(document.chapters)
    for document in documents
)

completed_documents = sum(
    1
    for document in documents
    if document.status == "completed"
)

top_col1, top_col2, top_col3 = st.columns(3)

top_col1.metric("歷史文件數", total_documents)
top_col2.metric("累積 Module 數", total_chapters)
top_col3.metric("完成匯出文件", completed_documents)

st.divider()
st.subheader("🗂️ 已分析文件")

document_options = {
    (
        f"{document.file_name}｜"
        f"{format_datetime(document.updated_at)}"
    ): document.id
    for document in documents
}

selected_label = st.selectbox(
    "選擇要查看的文件",
    options=list(document_options.keys()),
)

selected_document_id = document_options[selected_label]

selected_document = get_document_with_chapters(
    selected_document_id
)

if selected_document is None:
    st.error("找不到選擇的文件紀錄。")
    st.stop()

st.divider()
st.subheader(f"📄 {selected_document.file_name}")

info_col1, info_col2, info_col3, info_col4 = st.columns(4)

info_col1.metric(
    "文件格式",
    selected_document.file_extension.upper(),
)

info_col2.metric(
    "檔案大小",
    format_file_size(selected_document.file_size_bytes),
)

info_col3.metric(
    "頁數",
    selected_document.page_count,
)

info_col4.metric(
    "Module 數",
    selected_document.chapter_count,
)

detail_col1, detail_col2, detail_col3 = st.columns(3)

detail_col1.metric(
    "文字字數",
    f"{selected_document.character_count:,}",
)

detail_col2.metric(
    "文件狀態",
    status_label(selected_document.status),
)

detail_col3.metric(
    "最後更新",
    format_datetime(selected_document.updated_at),
)

if selected_document.notion_parent_url:
    st.link_button(
        "開啟 Notion 詳細學習筆記",
        selected_document.notion_parent_url,
    )
else:
    st.caption("此文件目前尚未保存 Notion 父頁連結。")

st.divider()
st.subheader("📚 Module 清單")

chapters = sorted(
    selected_document.chapters,
    key=lambda chapter: chapter.chapter_order,
)

if not chapters:
    st.info("這份文件尚未建立 Module 紀錄。")
    st.stop()

for chapter in chapters:
    title = (
        f"Module {chapter.chapter_order}｜"
        f"{chapter.title}"
    )

    with st.expander(title):
        st.caption(
            f"建立時間：{format_datetime(chapter.created_at)}｜"
            f"最後更新：{format_datetime(chapter.updated_at)}"
        )

        chapter_info_col1, chapter_info_col2 = st.columns(2)

        chapter_info_col1.metric(
            "字元數",
            f"{chapter.character_count:,}",
        )

        chapter_info_col2.metric(
            "SQLite Chapter ID",
            chapter.id[:8],
        )

        st.markdown("#### 狀態詳情")

        status_col1, status_col2, status_col3 = st.columns(3)

        with status_col1:
            show_status_card(
                title="匯出狀態",
                status=chapter.export_status,
                status_type="export",
            )

        with status_col2:
            show_status_card(
                title="圖片分析快取",
                status=chapter.visual_cache_status,
                status_type="visual_cache",
            )

        with status_col3:
            show_status_card(
                title="詳細筆記快取",
                status=chapter.note_cache_status,
                status_type="note_cache",
            )

        if chapter.notion_page_url:
            st.link_button(
                "開啟此 Module 的 Notion 頁面",
                chapter.notion_page_url,
            )
        else:
            st.caption("此 Module 目前尚未保存 Notion 子頁連結。")