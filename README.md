# AI Notion 筆記整理器

一套以 Python、Streamlit、OpenAI、Notion API 與 SQLite 建立的文件學習系統。它能解析 PDF、DOCX、TXT 和 Markdown，辨識主章節，生成結構化學習筆記，匯出成 Notion 子頁，並提供 Quiz、Flash Card、弱點追蹤和學習儀表板。

## 主要功能

- 多格式文件上傳與解析。
- 主章節、跨行標題和描述性標題偵測。
- Chunk 分析與整份內容合併。
- 逐章詳細筆記與 PDF 視覺分析。
- Markdown、JSON 和原生 Notion Blocks 匯出。
- Notion 父頁、章節子頁、Callout、Toggle、Code、Table 和 Image。
- 視覺/筆記快取與 Notion 失敗續跑。
- Quiz 作答、自評、錯題與 WeakPoint。
- Flash Card 翻卡、熟悉度與複習排程。
- 學習儀表板與 SQLite 資料診斷。
- 非破壞性重新分析、題目去重與舊快取回填。
- SQLite 持久化背景工作佇列，可離開目前頁面並查看進度。
- Windows 單一安裝 EXE、桌面捷徑與版本更新檢查。

## 一鍵啟動

完成環境安裝後，雙擊：

```text
啟動_AI筆記整理器.bat
```

Launcher 會檢查虛擬環境、必要套件和 SQLite Schema，尋找可用 Port，啟動 Streamlit 並開啟瀏覽器。

Launcher 也會啟動獨立背景 Worker。文件分析與整份 Notion 匯出會先寫入 SQLite 佇列，由 Worker 執行；切換頁面不會中斷工作，Worker 意外關閉後也會在下次啟動時恢復未完成工作。

也可以手動執行：

```powershell
.venv\Scripts\python.exe -m streamlit run AI_Notion_筆記整理器.py
```

## 安裝

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

在根目錄建立 `.env`：

```text
OPENAI_API_KEY=your_openai_api_key
NOTION_API_KEY=your_notion_integration_token
NOTION_PARENT_PAGE_ID=your_parent_page_id

OPENAI_CHUNK_MODEL=gpt-5-mini
OPENAI_MERGE_MODEL=gpt-5
MAX_FILE_SIZE_MB=25
CHUNK_SIZE=6000
CHUNK_OVERLAP=500
```

請勿將 `.env`、`.venv` 或 `outputs` 上傳到公開 Repository 或放入程式碼備份。

## 專案入口

```text
AI_Notion_筆記整理器.py        主工作台
pages/1_文件管理.py            文件管理
pages/2_quiz練習.py            Quiz 練習
pages/3_flash_card複習.py      Flash Card 複習
pages/4_學習儀錶板.py          學習統計
pages/5_資料管理與診斷.py      維護與修復
pages/6_背景工作.py            背景佇列、進度、取消與歷史
pages/7_關於與更新.py          版本資訊、更新檢查與安裝
launcher.py                    Windows 啟動器
background_worker.py           背景工作執行程序
```

## Windows 安裝版

開發者建置工具：

```powershell
.venv\Scripts\python.exe -m pip install -r requirements-build.txt
winget install --id JRSoftware.InnoSetup --exact
```

建立安裝程式：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_windows_release.ps1
```

完成檔案位於：

```text
release/AI_Notion_Note_Organizer_Setup.exe
```

這是一個單一安裝 EXE。它會安裝應用程式、建立開始功能表與可選桌面捷徑；執行時不需要 Python、VS Code 或專案虛擬環境。

安裝版的個人資料位於：

```text
%LOCALAPPDATA%\AI Notion Note Organizer\
```

首次使用時，依同目錄的 `.env.example` 建立 `.env` 並填入 API Key。安裝與更新不會把 `.env`、SQLite、快取或背景工作打包進程式，也不會在升級時刪除它們。

## 自動更新

應用程式啟動後會在背景讀取本專案固定的 GitHub latest Release，不需要設定 `APP_UPDATE_MANIFEST_URL`，也不需要另外上傳 Manifest。安裝檔必須使用固定名稱，下載後必須符合 GitHub Release Asset 提供的 SHA-256 digest，最後仍由使用者在「關於與更新」頁確認安裝。

建立本機 Release：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_windows_release.ps1
```

推送 `v3.0.1` 這類版本 Tag 後，GitHub Actions 會自動測試、建置並建立 Release。使用者固定使用以下一鍵下載網址：

```text
https://github.com/Allen1208tw/AI-notion-note-organizer/releases/latest/download/AI_Notion_Note_Organizer_Setup.exe
```

完整發布步驟見 [背景工作、Windows 封裝與自動更新](docs/14_background_jobs_and_windows_release.md)。

## 技術文件

從 [文件閱讀指南](docs/00_reading_guide.md) 開始。完整文件涵蓋系統架構、檔案職責、技術選型、Database Schema、資料流、Prompt、API、UI、開發路線、程式碼導讀和展示問答。

特別推薦：

- [系統架構](docs/02_system_architecture.md)
- [端到端資料流](docs/06_data_flow.md)
- [核心程式碼導讀](docs/12_code_walkthrough.md)
- [展示腳本與技術問答](docs/13_demo_and_technical_qa.md)

## 測試

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -v
.venv\Scripts\python.exe -m py_compile launcher.py AI_Notion_筆記整理器.py
```

目前穩定性測試重點包括：重複題目清理、作答/複習關聯保留、重新分析沿用章節 ID、背景 Job 序列化與恢復，以及 GitHub Release 來源與 SHA-256 驗證。

## 備份

程式碼備份應排除：

```text
.env
.venv/
outputs/
backups/
```

`outputs` 含 SQLite、快取和匯出狀態；若要備份個人學習資料，應另外建立加密且不公開的資料備份。

## 現況與限制

目前完成 Windows 單機發行版、SQLite 背景工作佇列與安全更新流程。SQLite、檔案快取和 Streamlit 適合個人使用；尚未提供多人帳號、雲端資料隔離與 Alembic Migration。雲端化路線請參考 `docs/10_development_roadmap.md`。
