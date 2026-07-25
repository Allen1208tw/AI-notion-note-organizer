from __future__ import annotations

import os
import time

import streamlit as st

from src.services.app_configuration_service import (
    get_configuration_status,
    request_application_restart,
    save_configuration,
)
from src.services.gemini_service import test_gemini_connection
from src.services.notion_service import get_notion_client
from src.services.openai_service import test_openai_connection


st.set_page_config(
    page_title="開始使用與設定",
    page_icon="⚙️",
    layout="wide",
)

st.title("⚙️ 開始使用與設定")
st.caption(
    "在這裡設定 AI API Key、Notion 連線、模型與分析參數。"
    "Key 只會保存在這台電腦，不會上傳到 GitHub。"
)

status = get_configuration_status()

provider_text = "Gemini" if status["ai_provider"] == "gemini" else "OpenAI"
st.info(
    f"目前 AI 供應商：**{provider_text}**。"
    "設定儲存後請按下重新啟動，讓主程式與背景工作一起讀取新設定。"
)

status_col1, status_col2, status_col3, status_col4 = st.columns(4)
status_col1.metric(
    "OpenAI",
    "已設定" if status["openai_configured"] else "未設定",
)
status_col2.metric(
    "Gemini",
    "已設定" if status["gemini_configured"] else "未設定",
)
status_col3.metric(
    "Notion Token",
    "已設定" if status["notion_api_configured"] else "未設定",
)
status_col4.metric(
    "Notion 父頁",
    "已設定" if status["notion_parent_configured"] else "未設定",
)

st.divider()

st.subheader("一鍵取得 API Key")
link_col1, link_col2, link_col3 = st.columns(3)
link_col1.link_button(
    "開啟 OpenAI API Keys",
    "https://platform.openai.com/api-keys",
    use_container_width=True,
)
link_col2.link_button(
    "開啟 Gemini API Key",
    "https://aistudio.google.com/app/apikey",
    use_container_width=True,
)
link_col3.link_button(
    "開啟 Notion Integrations",
    "https://www.notion.so/profile/integrations",
    use_container_width=True,
)

with st.expander("API Key 與 Notion 權限設定教學", expanded=True):
    st.markdown(
        """
### 1. OpenAI API Key

1. 點上方「開啟 OpenAI API Keys」。
2. 登入 OpenAI Platform。
3. 建立新的 API Key。
4. 複製後貼到下方 `OpenAI API Key`。

### 2. Gemini API Key

1. 點上方「開啟 Gemini API Key」。
2. 進入 Google AI Studio。
3. 建立 API Key。
4. 複製後貼到下方 `Gemini API Key`。
5. 若想免費或低成本生成完整筆記，可以把 AI 供應商選成 `Gemini`。

### 3. Notion Integration Token

1. 點上方「開啟 Notion Integrations」。
2. 建立一個新的 Integration，例如 `AI Notion Organizer`。
3. 複製 `Internal Integration Token`。
4. 貼到下方 `Notion Integration Token`。

### 4. Notion 父頁與 Integration 連線

1. 在 Notion 建立一個空白頁，例如 `AI 學習筆記`。
2. 打開該頁右上角 `...`。
3. 選擇 `Connections`。
4. 點 `+ Add connection` 或 `Add connections`。
5. 搜尋並選擇剛剛建立的 Integration。
6. 確認 Integration 可以存取這個頁面與子頁。
7. 複製這個 Notion 頁面的完整網址。
8. 貼到下方 `Notion 父頁網址或 Page ID`。

如果頁面右上角 `...` 裡找不到 `Connections`：

1. 回到 Notion Integrations 頁面。
2. 點進你的 Integration。
3. 打開 `Content access`。
4. 點 `Edit access`。
5. 選取要作為父頁的 Notion 頁面並儲存。

如果出現 `Could not find page`，通常代表父頁還沒有分享給該 Integration，
或貼到不同 Workspace 的頁面。
"""
    )

with st.form("application_configuration_form"):
    st.subheader("API 與 Notion")

    ai_provider_label = st.radio(
        "AI 供應商",
        options=["OpenAI", "Gemini"],
        index=1 if status["ai_provider"] == "gemini" else 0,
        horizontal=True,
        help=(
            "選 Gemini 時，文件摘要、詳細筆記、Quiz、Flash Card、"
            "Mermaid 與 PDF 圖片分析都會改由 Gemini 產生。"
        ),
    )
    ai_provider = "gemini" if ai_provider_label == "Gemini" else "openai"

    openai_api_key = st.text_input(
        "OpenAI API Key",
        type="password",
        placeholder="貼上 sk-... 或 OpenAI Project API Key",
        help="空白儲存會保留原本已設定的 Key。",
    )
    clear_openai_key = st.checkbox("清除已儲存的 OpenAI API Key")

    gemini_api_key = st.text_input(
        "Gemini API Key",
        type="password",
        placeholder="貼上 Google AI Studio 產生的 Gemini API Key",
        help="空白儲存會保留原本已設定的 Key。",
    )
    clear_gemini_key = st.checkbox("清除已儲存的 Gemini API Key")

    notion_api_key = st.text_input(
        "Notion Integration Token",
        type="password",
        placeholder="貼上 ntn_... 或 secret_... Token",
        help="這是 Notion Integration 的 Internal Integration Token，不是頁面網址。",
    )
    clear_notion_key = st.checkbox("清除已儲存的 Notion Token")

    notion_parent_page = st.text_input(
        "Notion 父頁網址或 Page ID",
        value=status["notion_parent_page_id"],
        placeholder="貼上 Notion 父頁完整網址，或 32 位 Page ID",
        help="請先把該父頁分享給你的 Notion Integration，再貼上頁面網址。",
    )

    with st.expander("進階參數"):
        openai_chunk_model = st.text_input(
            "OpenAI 分段分析模型",
            value=status["openai_chunk_model"],
        )
        openai_merge_model = st.text_input(
            "OpenAI 合併摘要 / 詳細筆記模型",
            value=status["openai_merge_model"],
        )
        gemini_detail_model = st.text_input(
            "Gemini 詳細筆記模型",
            value=status["gemini_detail_model"],
            help="目前建議使用 gemini-3.5-flash。",
        )
        max_file_size_mb = st.number_input(
            "最大檔案大小 MB",
            min_value=1,
            max_value=500,
            value=status["max_file_size_mb"],
            step=1,
        )
        chunk_size = st.number_input(
            "Chunk 大小",
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
            "自動下載新版安裝檔",
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
        st.success(
            "設定已儲存。請按下重新啟動，讓主程式與背景工作套用新設定。"
        )
    except Exception as error:
        st.error(f"設定儲存失敗：{error}")

if st.session_state.get("configuration_saved"):
    if st.button("套用設定並重新啟動", type="primary"):
        request_application_restart()
        st.info("正在重新啟動，瀏覽器會自動重新連線...")
        time.sleep(0.5)
        os._exit(0)

st.divider()

st.subheader("連線測試")
st.caption(
    "Notion API 測試只確認 Token 能連上 Notion。"
    "若整份匯出時出現 Could not find page，請回去確認父頁已分享給 Integration。"
)

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
            st.success(
                "Notion Token 連線成功。若要匯出頁面，仍需確認父頁已分享給 Integration。"
            )
        except Exception as error:
            st.error(f"Notion 連線失敗：{error}")

st.warning(
    "請不要把 `.env`、API Key、Notion Token、SQLite 資料庫或 outputs 資料夾上傳到 GitHub。"
)
