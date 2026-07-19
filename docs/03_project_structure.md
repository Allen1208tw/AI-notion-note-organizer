# 專案結構與檔案職責

## 根目錄

| 檔案或目錄 | 工作 |
|---|---|
| `AI_Notion_筆記整理器.py` | Streamlit 首頁、文件上傳、分析結果、Notion 整份匯出流程 |
| `launcher.py` | 一鍵啟動、依賴與 Schema 檢查、Port 選擇、瀏覽器開啟 |
| `background_worker.py` | 從 SQLite 佇列領取文件分析與 Notion 匯出工作 |
| `啟動_AI筆記整理器.bat` | Windows 雙擊入口，呼叫虛擬環境中的 Python |
| `pages/` | Streamlit 多頁功能 |
| `src/` | 核心程式碼 |
| `tests/` | 自動化測試 |
| `outputs/` | SQLite、快取、匯出狀態與輸出檔；不應進 Git 或程式備份 |
| `docs/` | 架構、開發與教學文件 |
| `packaging/` | PyInstaller 與 Inno Setup 發行規格 |
| `scripts/` | Windows Release 建置工具 |
| `.github/workflows/windows-release.yml` | 版本 Tag 觸發測試、封裝與 GitHub Release 發布 |

## Pages

| 頁面 | 功能 |
|---|---|
| `pages/0_開始使用與設定.py` | 首次使用說明、API Key、Notion 與分析參數設定 |
| `pages/1_文件管理.py` | 文件清單、狀態、儲存空間與刪除 |
| `pages/2_quiz練習.py` | 依文件及章節練習 Quiz、顯示答案、自評、錯題與紀錄 |
| `pages/3_flash_card複習.py` | 依章節翻卡、熟悉度評分、卡片總覽與複習紀錄 |
| `pages/4_學習儀錶板.py` | Quiz、Flash Card、弱點與近期活動整合統計 |
| `pages/5_資料管理與診斷.py` | 資料健康檢查、章節分布、去重、清除與快取同步 |
| `pages/6_背景工作.py` | 背景工作狀態、進度、取消與終止工作清理 |
| `pages/7_關於與更新.py` | 版本、更新檢查、下載驗證與啟動安裝程式 |

頁面只負責互動與顯示。任何可重用的資料查詢或更新都應放入 `src/services/`。

## Config 與 Database

| 檔案 | 功能 |
|---|---|
| `src/config/settings.py` | 讀取 `.env`、模型名稱、檔案限制、Chunk 參數與輸出路徑 |
| `src/database/database.py` | SQLAlchemy Engine、Base 與 Session Context Manager |
| `src/database/models.py` | 所有 ORM Table、關聯、唯一限制與預設值 |
| `src/database/init_db.py` | 建立資料表並檢查舊資料庫缺少的 Schema |
| `src/services/app_configuration_service.py` | 讀寫本機 `.env`、驗證參數與要求完整重啟 |

## Parsers 與 Processors

| 檔案 | 功能 |
|---|---|
| `pdf_parser.py` | 以 PyMuPDF 擷取 PDF 文字與頁數 |
| `docx_parser.py` | 讀取 Word 段落與表格文字 |
| `text_parser.py` | 讀取 TXT |
| `markdown_parser.py` | 讀取 Markdown |
| `text_cleaner.py` | 統一空白與雜訊，保留可分析內容 |
| `text_chunker.py` | 依大小與重疊切分長文件 |
| `chapter_detector.py` | 偵測 Module/Chapter/第 N 章、目錄映射、跨行標題與正文範圍 |
| `pdf_visual_extractor.py` | 將 PDF 頁面轉成可供視覺分析的圖片資料 |

`src/processors/learning_database.py` 是早期相容檔或技術債，現行資料庫流程應以 `src/services/learning_database_service.py` 為準。新增功能不要再依賴前者。

## Pydantic Models

| 檔案 | 功能 |
|---|---|
| `analysis_models.py` | Chunk 分析與整份文件合併結果 |
| `chapter_models.py` | 詳細章節筆記、術語、程式碼、Quiz、Flash Card 等結構 |

Pydantic Model 是 AI JSON 與應用程式之間的契約。提示詞要求的欄位、驗證 Model 和 Notion Builder 必須同步修改。

## Prompts

| 檔案 | 功能 |
|---|---|
| `system_prompt.py` | 全域角色與輸出原則 |
| `chunk_prompt.py` | 單一文字 Chunk 分析 |
| `merge_prompt.py` | 合併多個 Chunk 的結果 |
| `chapter_prompt.py` | 生成完整章節學習筆記 |
| `summary_quality_prompt.py` | 摘要品質檢查或改善 |
| `mermaid_quality_prompt.py` | Mermaid 品質檢查 |
| `mermaid_repair_prompt.py` | 修復無效 Mermaid |
| `notion_service.py` | 與 Notion 內容生成相關的提示或轉換支援 |

## Services

| 檔案 | 功能 |
|---|---|
| `openai_service.py` | 建立與共用 OpenAI Client |
| `analysis_service.py` | Chunk 分析、合併、JSON 重試與整份結果驗證 |
| `chapter_service.py` | 單章詳細筆記生成與驗證 |
| `pdf_visual_service.py` | 選頁、圖片分析與視覺上下文 |
| `chapter_cache_service.py` | 視覺與詳細筆記快取、舊格式 fallback |
| `export_state_service.py` | Notion 父頁與章節成功/失敗續跑狀態 |
| `notion_service.py` | 基本 Notion 操作 |
| `chapter_notion_service.py` | 詳細 Notion Blocks、子頁、圖片、Toggle、快取與 SQLite 同步 |
| `learning_database_service.py` | 文件/章節 Upsert、學習項目合併、統計與刪除 |
| `learning_item_identity.py` | Quiz 與 Flash Card 正規化識別鍵 |
| `quiz_practice_service.py` | Quiz 查詢、作答、自評與 WeakPoint 更新 |
| `flashcard_practice_service.py` | 翻卡資料、熟悉度與複習排程 |
| `learning_dashboard_service.py` | 跨 Quiz、Flash Card 與弱點統計 |
| `learning_data_admin_service.py` | 診斷、重複清理、章節/文件維護 |
| `export_estimate_service.py` | Token 或匯出成本估算 |
| `file_validator.py` | 副檔名、大小等上傳驗證 |

## Exporters 與 Validators

| 檔案 | 功能 |
|---|---|
| `markdown_builder.py` | 將分析結果轉成 Markdown |
| `json_exporter.py` | 將結果輸出成 JSON |
| `mermaid_validator.py` | 檢查 Mermaid 結構，必要時交給修復流程 |

## 找程式碼的實用方法

遇到「按鈕在哪裡」先查 `pages/` 或主入口；遇到「按下後如何處理」查該頁 import 的 Service；遇到「資料存在哪裡」查 `models.py` 與 Database Service；遇到「AI 為何產生這種格式」查 Prompt 與 Pydantic Model；遇到「Notion 為何長這樣」查 `chapter_notion_service.py` 的 Block Builder。
