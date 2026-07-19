from __future__ import annotations

import os
import time

import streamlit as st

from src.services.notion_service import get_notion_client
from src.services.gemini_service import test_gemini_connection
from src.services.openai_service import test_openai_connection
from src.services.app_configuration_service import (
    get_configuration_status,
    request_application_restart,
    save_configuration,
)


st.set_page_config(
    page_title="開始使用與設定",
    page_icon="⚙️",
    layout="wide",
)

st.title("⚙️ 開始使用與設定")
st.caption("API Key 只保存在這台電腦，不會寫入安裝程式或上傳到 GitHub。")

status = get_configuration_status()

st.caption(
    "目前 AI 供應商："
    f"{'Gemini' if status['ai_provider'] == 'gemini' else 'OpenAI'}｜"
    f"Gemini：{'已設定' if status['gemini_configured'] else '未設定'}"
)

status_col1, status_col2, status_col3 = st.columns(3)
status_col1.metric("OpenAI", "已設定" if status["openai_configured"] else "未設定")
status_col2.metric(
    "Notion API",
    "已設定" if status["notion_api_configured"] else "未設定",
)
status_col3.metric(
    "Notion 父頁",
    "已設定" if status["notion_parent_configured"] else "未設定",
)

st.info(
    "OpenAI API Key 是文件分析必要設定。Notion API Key 與父頁只在需要匯出 "
    "Notion 時才需要。已儲存的 Key 不會重新顯示在畫面上。"
)

with st.form("application_configuration_form"):
    st.subheader("API 與 Notion")
    openai_api_key = st.text_input(
        "OpenAI API Key",
        type="password",
        placeholder="留空會保留既有 Key",
    )
    clear_openai_key = st.checkbox("清除已儲存的 OpenAI API Key")

    ai_provider_label = st.radio(
        "AI 供應商",
        options=["OpenAI", "Gemini"],
        index=1 if status["ai_provider"] == "gemini" else 0,
        horizontal=True,
        help="選 Gemini 後，文件摘要、詳細筆記與 PDF 視覺分析都會改用 Gemini。",
    )
    ai_provider = "gemini" if ai_provider_label == "Gemini" else "openai"

    gemini_api_key = st.text_input(
        "Gemini API Key",
        type="password",
        placeholder="貼上 Google AI Studio 產生的 Gemini API Key",
    )
    clear_gemini_key = st.checkbox("清除已儲存的 Gemini API Key")

    notion_api_key = st.text_input(
        "Notion Integration Token",
        type="password",
        placeholder="留空會保留既有 Token",
    )
    clear_notion_key = st.checkbox("清除已儲存的 Notion Token")
    notion_parent_page = st.text_input(
        "Notion 父頁網址或 Page ID",
        value=status["notion_parent_page_id"],
        help="請先把父頁分享給你的 Notion Integration。",
    )

    with st.expander("進階分析參數"):
        openai_chunk_model = st.text_input(
            "分段分析模型",
            value=status["openai_chunk_model"],
        )
        openai_merge_model = st.text_input(
            "整體合併與詳細筆記模型",
            value=status["openai_merge_model"],
        )
        gemini_detail_model = st.text_input(
            "Gemini 筆記生成模型",
            value=status["gemini_detail_model"],
            help="建議先用 gemini-3.5-flash；若免費額度或模型名稱改變，可在這裡調整。",
        )
        max_file_size_mb = st.number_input(
            "最大上傳檔案大小（MB）",
            min_value=1,
            max_value=500,
            value=status["max_file_size_mb"],
            step=1,
        )
        chunk_size = st.number_input(
            "Chunk 大小（字元）",
            min_value=1000,
            max_value=100000,
            value=status["chunk_size"],
            step=500,
        )
        chunk_overlap = st.number_input(
            "Chunk 重疊字數",
            min_value=1,
            max_value=20000,
            value=status["chunk_overlap"],
            step=100,
        )
        auto_download_updates = st.checkbox(
            "發現新版時自動下載（安裝前仍會詢問）",
            value=status["auto_download_updates"],
        )

    submitted = st.form_submit_button("儲存設定", type="primary")

if submitted:
    try:
        status = save_configuration(
            openai_api_key=openai_api_key,
            gemini_api_key=gemini_api_key,
            notion_api_key=notion_api_key,
            notion_parent_page=notion_parent_page,
            ai_provider=ai_provider,
            openai_chunk_model=openai_chunk_model,
            openai_merge_model=openai_merge_model,
            gemini_detail_model=gemini_detail_model,
            max_file_size_mb=int(max_file_size_mb),
            chunk_size=int(chunk_size),
            chunk_overlap=int(chunk_overlap),
            auto_download_updates=auto_download_updates,
            clear_openai_key=clear_openai_key,
            clear_gemini_key=clear_gemini_key,
            clear_notion_key=clear_notion_key,
        )
        st.session_state["configuration_saved"] = True
        st.success("設定已安全儲存。重新啟動後，所有頁面會使用新設定。")
    except Exception as error:
        st.error(f"設定無法儲存：{error}")

if st.session_state.get("configuration_saved"):
    if st.button("套用設定並重新啟動", type="primary"):
        request_application_restart()
        st.info("正在重新啟動，瀏覽器會自動重新連線...")
        time.sleep(0.5)
        os._exit(0)

st.divider()
st.subheader("取得設定值")
st.markdown(
    "1. **OpenAI API Key**：到 OpenAI Platform 建立 API Key，這是 AI 分析必要項目。\n"
    "2. **Notion Integration Token**：到 Notion Integrations 建立 Integration。\n"
    "3. **Notion 父頁**：建立一個空白頁，分享給 Integration，再貼上頁面網址。\n"
    "4. 儲存後按下重新啟動，之後可直接從首頁上傳文件。"
)
link_col1, link_col2 = st.columns(2)
link_col1.link_button(
    "開啟 OpenAI API Keys",
    "https://platform.openai.com/api-keys",
    use_container_width=True,
)
link_col2.link_button(
    "開啟 Notion Integrations",
    "https://www.notion.so/profile/integrations",
    use_container_width=True,
)

st.subheader("連線測試")
test_col1, test_col2, test_col3 = st.columns(3)
if test_col1.button("測試 OpenAI 連線", use_container_width=True):
    if not status["openai_configured"]:
        st.error("請先儲存 OpenAI API Key 並重新啟動。")
    else:
        try:
            with st.spinner("正在測試 OpenAI..."):
                message = test_openai_connection()
            st.success(message or "OpenAI API 連線成功。")
        except Exception as error:
            st.error(f"OpenAI 連線失敗：{error}")

if test_col2.button("測試 Gemini 連線", use_container_width=True):
    if not status["gemini_configured"]:
        st.error("請先儲存 Gemini API Key 並重新啟動。")
    else:
        try:
            with st.spinner("正在測試 Gemini..."):
                message = test_gemini_connection()
            st.success(message or "Gemini API 連線成功。")
        except Exception as error:
            st.error(f"Gemini 連線失敗：{error}")

if test_col3.button("測試 Notion 連線", use_container_width=True):
    if not (
        status["notion_api_configured"]
        and status["notion_parent_configured"]
    ):
        st.error("請先儲存 Notion Token 與父頁，並重新啟動。")
    else:
        try:
            with st.spinner("正在測試 Notion..."):
                get_notion_client().users.me()
            st.success("Notion API 連線成功。")
        except Exception as error:
            st.error(f"Notion 連線失敗：{error}")

st.warning(
    "`.env` 是本機純文字設定檔。不要寄給別人、不要上傳 GitHub，也不要放進公開備份。"
)
