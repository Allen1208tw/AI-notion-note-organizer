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

## 最新修正

### v3.2.7

- 修正 HTML 講義中多個主章節使用相同標題時難以辨識的問題。
- 同名主章節現在會保留完整章節，不會誤刪或合併，並自動補上章內主題，例如 `CSS樣式屬性｜背景樣式一、背景樣式二`。
- 已確認不影響 Python 基礎 + PyMySQL 講義分章，仍維持 14 章主章節。
- 新增回歸測試，防止同名章節再次退回難以辨識的狀態。

### v3.2.6

- 「開始使用與設定」頁新增 OpenAI、Gemini、Notion 的一鍵跳轉按鈕。
- Gemini API Key 可直接從設定頁開啟 Google AI Studio API Key 頁面取得。
- Notion 設定區加入完整操作教學，說明 Integration Token、父頁網址與新版 `... → Connections → Add connection` 權限設定。
- 連線測試區補充提醒：Notion Token 成功不代表父頁已授權，若出現 `Could not find page`，通常要回 Notion 父頁右上角 `...` 把 Integration 加入 Connections。
- 安裝版 `使用說明.txt` 改為完整中文教學，包含 API Key 取得方式、Notion 連線步驟、常見錯誤與資料保存位置。

### v3.2.5

- 修正 MySQL 教材中 SQL 日期範圍、官方文件編號與 `NULL Values` 被誤判成子章節的問題。
- 編號型子章節現在必須屬於目前主章節，例如第 4 章只接受 `4.1` / `4-1` 這類小節，不會把 `1970-01-01`、`9.1.7` 等資料內容當成小節。
- 新增多種章節偵測測試樣本：SQL 範例干擾、清楚 `1.1` 小節、清楚 `Section` 小節、無明確小節的投影片格式。

### v3.2.4

- 修正《機器學習數學》偵測 3 章但只產出部分筆記的章節/子章節切分問題。
- 子章節偵測會優先讀取章節開頭目錄，例如線性代數 4 節、微分 6 節、統計 2 節，不再把每張投影片小標題都切成獨立筆記。
- Notion 詳細筆記可自選生成範圍：勾主章節會濃縮整章，勾子章節會獨立生成更精細筆記。
- 自選主章節與子章節都會建立在同一份文件父頁底下，子頁標題會標明「第 X 章」或「子章節 X-Y」。
- 子章節 Quiz/Flash Cards 會自動建立 SQLite 子章節紀錄並正確保存，不會因找不到主章節 ID 而遺失。
- 新增 5 份主章節/子章節偵測測試樣本，涵蓋英文 Module、中文第 X 章、`1.1` 小節、重複章節標題與投影片目錄格式。
- 子章節偵測改為保守模式：若章節內沒有清楚的目錄或小節標題，系統只產生主章節筆記，不會把頁碼、圖片說明、程式碼或投影片短句誤切成子章節。

### v3.2.3

- 修正同一份教材內含多組章節序列時，只保留第一組的問題。
- 章節偵測現在可同時保留 `Python Module 1～10` 與後續 `PyMySQL Chapter 1～4`。
- 泛用標題如 `Chapter1` 會優先讀取下一行真實標題，例如 `PyMySQL 介紹`，避免誤套前方目錄的 Module 標題。

### v3.2.0

- Added selectable AI provider support: OpenAI or Gemini.
- Gemini mode can run the full note generation pipeline, including document summary/chunk analysis, chapter detailed notes, Quiz/Flash Cards, Mermaid content, and PDF visual page analysis.
- Added `AI_PROVIDER`, `GEMINI_API_KEY`, and `GEMINI_DETAIL_MODEL` configuration fields.
- Added Gemini connection test in the setup page and packaged `google-genai` for Windows release builds.

### v3.2.1

- 改善 Windows 安裝檔的覆蓋更新流程。
- 使用者已安裝舊版時，可直接執行新版 `AI_Notion_Note_Organizer_Setup.exe` 進行原地更新。
- 更新會替換程式檔案，但保留 AppData 裡的 API Key、SQLite、快取、輸出檔案與背景工作狀態。
- 安裝程式會先關閉正在執行的舊版程式，避免檔案被鎖住而更新失敗。

### v3.2.2

- 修正 Notion 匯出完成判斷，避免 17 章只產生部分章節卻顯示完成。
- 章節必須實際記錄 Notion 頁面 ID 或 URL，才會被視為完成。
- 背景匯出結果會顯示本次使用的 AI 供應商與模型，例如 `Gemini｜gemini-3.5-flash`。
- 「開始整份 Notion 匯出」會強制重新呼叫 AI 生成全新筆記與圖片分析。
- 「繼續未完成的 Notion 匯出」才會沿用既有快取。

### v3.1.5

- Fixed Notion export completion cleanup when `completed_chapters` or `failed_chapters` are stored as strings or numbers instead of dictionaries.
- Successful background or foreground Notion exports no longer show `'str' object has no attribute 'get'` after the pages have already been created.
- When the same chapter appears in both completed and failed lists from an older export state, completed status wins so the UI reports the real finished state.

### v3.1.1

- 修正安裝版生成詳細筆記時，後續章節誤用第 1 章快取，導致所有 Notion 子頁內容都像第 1 章的問題。
- 章節快取 fallback 現在必須符合 `chapter_id`、`source_chapter_id`、`chapter_order` 或章節標題，不會因為資料夾裡只有一個快取檔就直接套用。
- Mermaid 學習地圖改用 Notion 官方支援的 `mermaid` code block language，並自動移除 AI 可能產生的 Markdown code fence，讓 Notion 優先以圖表方式呈現。
- 新增回歸測試，避免單一快取檔再次被錯誤套用到其他章節。

### v3.1.2

- 主頁重新開啟時會自動從 SQLite 找回等待中或執行中的背景工作。
- 即使瀏覽器分頁關掉後再打開，主頁上方也會顯示「目前仍有背景工作在執行」與進度入口。
- 這項修正避免使用者誤以為關掉網頁後文件分析或 Notion 匯出被重置。

### v3.1.3

- 安裝版會固定優先使用 `%LOCALAPPDATA%\AI Notion Note Organizer\.env` 作為個人設定檔。
- 若舊版曾把 `.env` 放在安裝目錄，新版啟動時會自動複製到 AppData，讓 OpenAI API Key、Notion Token 和父頁設定在重新下載或更新後保留下來。
- 已補上設定檔搬家測試，避免更新流程再次造成 API 設定遺失。

### v3.1.4

- PDF 視覺分析圖片會另存為圖片檔案快取，Notion 匯出時會建立真正的 image block，不再只留下圖片解讀文字。
- 舊視覺快取若只有頁碼和文字、沒有圖片本體，且背景工作仍有原始 PDF，系統會依頁碼重新渲染圖片，不重跑 AI。
- 主頁與「背景工作」頁改為自動刷新工作進度，不需要手動按「更新狀態」。
- Mermaid 學習地圖會安全化節點標籤內的 HTML/CSS 特殊符號，降低 `<div>`、`#id`、`|`、`:` 等內容造成 Notion 圖表無法渲染的機率。

## 一鍵啟動

完成環境安裝後，雙擊：

```text
啟動_AI筆記整理器.bat
```

Launcher 會檢查虛擬環境、必要套件和 SQLite Schema，尋找可用 Port，啟動 Streamlit 並開啟瀏覽器。

Launcher 也會啟動獨立背景 Worker。文件分析與整份 Notion 匯出會先寫入 SQLite 佇列，由 Worker 執行；切換頁面不會中斷工作，Worker 意外關閉後也會在下次啟動時恢復未完成工作。

## 首次使用設定

安裝版啟動後，從左側開啟「開始使用與設定」。網頁可直接輸入並保存：

- OpenAI API Key：文件分析必要。
- Notion Integration Token：只有匯出 Notion 時需要。
- Notion 父頁網址或 Page ID：可直接貼完整網址。
- 分段分析模型與整體合併模型。
- 最大檔案大小、Chunk 大小與重疊字數。
- 是否自動下載更新。

API Key 使用密碼欄位，不會回填到畫面。設定寫入 `%LOCALAPPDATA%\AI Notion Note Organizer\.env`，按「套用設定並重新啟動」後，Streamlit 與背景 Worker 會一起重新載入設定。安裝目錄另附 `使用說明.txt`，開始功能表也有使用說明捷徑。

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
pages/0_開始使用與設定.py      API Key、Notion、模型與分析參數
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

首次使用時，依同目錄的 `.env.example` 建立 `.env` 並填入 API Key。安裝與更新不會把 `.env`、SQLite、快取或背景工作打包進程式，也不會在升級時刪除它們。新版安裝檔可直接覆蓋舊版安裝，安裝程式會先關閉舊版程式，再替換安裝目錄內的執行檔與 `_internal` 程式資源。

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
