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
- Windows 雙擊啟動。

## 一鍵啟動

完成環境安裝後，雙擊：

```text
啟動_AI筆記整理器.bat
```

Launcher 會檢查虛擬環境、必要套件和 SQLite Schema，尋找可用 Port，啟動 Streamlit 並開啟瀏覽器。

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
launcher.py                    Windows 啟動器
```

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

目前穩定性測試重點包括：重複題目清理、作答/複習關聯保留、重新分析沿用章節 ID，以及非破壞性同步。

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

目前完成到 V2.5，定位是 Windows 單機應用。SQLite、檔案快取和 Streamlit 很適合個人使用，但尚未提供多人帳號、雲端資料隔離、背景工作佇列和正式資料庫 Migration。雲端化路線請參考 `docs/10_development_roadmap.md`。
