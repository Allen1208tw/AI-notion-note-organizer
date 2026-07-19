# 技術選型

## 技術總表

| 類別 | 技術 | 專案用途 |
|---|---|---|
| 語言 | Python | 串接 AI、文件解析、資料庫與 UI |
| UI | Streamlit | 快速建立多頁互動式資料應用 |
| AI | OpenAI API | 文件理解、摘要、章節筆記與視覺分析 |
| 驗證 | Pydantic | 驗證 AI 結構化 JSON |
| ORM | SQLAlchemy 2.x | Model、關聯、查詢與交易 |
| 資料庫 | SQLite | 單機持久化學習資料 |
| PDF | PyMuPDF | PDF 文字擷取與頁面渲染 |
| DOCX | python-docx | Word 文件解析 |
| Notion | Notion API / notion-client | 建立父頁、子頁與原生 Blocks |
| 設定 | python-dotenv | 從 `.env` 讀取 Token 與參數 |
| HTTP | requests | Notion 圖片上傳等 HTTP 操作 |
| 圖表 | Streamlit 原生 Chart | 儀表板統計視覺化 |
| 啟動 | Batch + Python launcher | Windows 一鍵開啟應用程式 |
| 背景工作 | SQLite Queue + Worker Process | 持久化耗時工作、進度、取消與中斷恢復 |
| 封裝 | PyInstaller | 將 Python 與相依套件封裝成可執行目錄 |
| 安裝 | Inno Setup | 產生單一 Windows 安裝 EXE 與捷徑 |
| 更新 | GitHub Releases API + SHA-256 | 零設定檢查、下載並驗證新版安裝程式 |

## 為什麼用 Streamlit

此專案是資料與 AI 工作流工具，核心互動包含檔案上傳、進度顯示、表單、分頁、指標與圖表。Streamlit 能直接使用 Python 資料物件，不需要另外維護 JavaScript 前端與 REST API，因此適合原型與單機版。

限制是每次互動會重新執行頁面，因此必須正確設計 `st.session_state`、唯一 Widget Key 和資料庫持久化。曾出現的卡片不換頁、按鈕 ID 重複與 Selectbox 狀態問題，都屬於 Streamlit rerun 模型下的典型課題。

## 為什麼用 SQLite 與 SQLAlchemy

SQLite 無須安裝資料庫伺服器，資料可跟著單機應用保存。SQLAlchemy 讓程式以 Model 和 Session 操作資料，也保留未來遷移 PostgreSQL 的可能。

選擇代價是：SQLite 不適合大量多人同時寫入，`create_all()` 也不會自動修改既有資料表，所以專案額外加入 Schema 檢查。正式雲端版應導入 PostgreSQL 與 Alembic Migration。

## 為什麼用 Pydantic

語言模型輸出不是天然可靠的 API Response。即使提示詞要求 JSON，仍可能缺欄位、型別錯誤或夾帶說明文字。Pydantic 將 AI 輸出轉成明確資料契約，使後續 Notion、SQLite 和 UI 不必處理任意形狀資料。

## 為什麼採兩階段 AI 分析

長文件無法穩定一次分析，因此先將文字切成有重疊的 Chunk，各自抽取重點，再合併成整份結果。詳細章節筆記則以 Chapter 為單位生成，讓內容範圍、Quiz 與 Flash Card 都能對應到正確章節。

## 模型設定策略

`OPENAI_CHUNK_MODEL` 預設用較適合大量局部工作的模型，`OPENAI_MERGE_MODEL` 用於跨 Chunk 整合。模型名稱放在 `.env`，避免寫死在業務程式，也方便依成本與品質調整。

## 快取技術選擇

視覺分析與章節筆記使用 JSON 檔，而非直接塞入 SQLite，因為它們是體積較大、可重建的中間產物。業務紀錄則存 SQLite，因為作答和複習歷史不可由原文件重建。

快取為避免檔案過大，可能移除 Base64 圖片資料；這代表舊快取能重建文字筆記，但不一定能重新上傳原圖到 Notion。這是一項明確的空間與完整性取捨。

## Notion 原生 Blocks

專案不是只輸出一大段 Markdown，而是建立 Heading、Callout、Toggle、Code、Table、Image 等原生 Blocks。優點是頁面可互動、可折疊且接近手工筆記；代價是要處理 Block 限制、Rich Text 長度、父子關係、圖片上傳與 API 錯誤。

## Windows 啟動方案

目前不是把整個專案封裝成單一 EXE，而是用 `.bat` 呼叫 `launcher.py`。Launcher 再使用 `.venv` 啟動 Streamlit。這個方案保留現有開發環境，容易除錯且不必每次開 VS Code。

## 安全與機密資料

OpenAI Key 與 Notion Token 存在 `.env`，備份與版本控制應排除 `.env`、`.venv` 和 `outputs`。程式與文件可以分享，但真正 Token、SQLite 使用資料和快取不應一起公開。

## 未來技術替換路線

| 現況 | 雲端版建議 |
|---|---|
| Streamlit 單體 UI | 保留 Streamlit 或改 React + FastAPI |
| SQLite | PostgreSQL |
| 本機 JSON 快取 | S3 相容物件儲存 + Redis/DB metadata |
| 同步長任務 | Celery/RQ/雲端工作佇列 |
| 單一使用者 | OAuth/Email Login + tenant/user_id |
| Batch Launcher | Docker + CI/CD + HTTPS Hosting |

## AI 供應商切換

`AI_PROVIDER` 可選 `openai` 或 `gemini`。選擇 `gemini` 後，文件 Chunk 摘要、合併摘要、章節詳細筆記、Quiz、Flash Cards、Mermaid 內容，以及 PDF 圖片視覺分析都會改由 Gemini 產生。OpenAI 模式仍保留作為高品質或備援選項。

Gemini 相關設定：

```text
AI_PROVIDER=gemini
GEMINI_API_KEY=your_gemini_api_key
GEMINI_DETAIL_MODEL=gemini-3.5-flash
```

Gemini SDK 使用 `google-genai`。設定頁會儲存 Gemini Key 到 AppData 的 `.env`，封裝版也會把 SDK 一起包入安裝檔。

## Windows 安裝與更新

Windows 版本使用 PyInstaller 打包執行檔，並用 Inno Setup 建立單一安裝程式。安裝程式使用固定 `AppId` 與固定安裝目錄，因此使用者下載新版 `AI_Notion_Note_Organizer_Setup.exe` 後，可以直接執行新版安裝檔覆蓋更新。

更新時只替換 `{localappdata}\Programs\AI Notion Note Organizer` 裡的程式檔案，不會刪除 `{localappdata}\AI Notion Note Organizer` 內的使用者資料。API Key、SQLite、快取、輸出檔案與背景工作狀態會保留下來。
