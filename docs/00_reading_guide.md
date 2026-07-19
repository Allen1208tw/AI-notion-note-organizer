# 專案技術文件閱讀指南

這套文件的目的不是只記錄「有哪些功能」，而是協助開發者完整說明：系統為什麼這樣設計、資料如何流動、每個檔案負責什麼，以及遇到技術追問時如何回答。

## 建議閱讀順序

1. `01_project_overview.md`：理解產品問題、使用者與核心價值。
2. `02_system_architecture.md`：掌握分層架構與模組互動。
3. `03_project_structure.md`：把功能對應到實際檔案。
4. `04_tech_stack.md`：理解每項技術的選擇理由。
5. `05_database_design.md`：理解 SQLite Schema、外鍵與資料生命週期。
6. `06_data_flow.md`：追蹤文件、AI、Notion 與練習資料的完整流程。
7. `07_prompt_design.md`：理解 AI 提示詞、結構化輸出與驗證策略。
8. `08_api_design.md`：理解 OpenAI、Notion 與服務層介面。
9. `09_ui_ux_design.md`：理解 Streamlit 頁面與狀態管理。
10. `10_development_roadmap.md`：理解版本演進與架構決策。
11. `11_sprint_planning.md`：理解如何拆解、驗證與交付功能。
12. `12_code_walkthrough.md`：用程式入口逐段對照實際功能。
13. `13_demo_and_technical_qa.md`：準備展示、口頭說明與常見技術問答。
14. `14_background_jobs_and_windows_release.md`：理解背景佇列、EXE 封裝、安裝與自動更新。

## 三種使用方式

### 快速展示前

閱讀 `01`、`02`、`06`、`13`。你應能在五分鐘內說明產品目的、技術流程與特色。

### 程式碼面試前

閱讀 `03`、`05`、`07`、`08`、`12`。重點是說清楚分層、交易、快取、外鍵與錯誤處理。

### 繼續開發前

閱讀 `10`、`11`，再依功能回查 `03` 和 `12`，避免把新邏輯放錯模組。

## 一句話介紹

AI Notion Note Organizer 是一套以 Streamlit 為操作介面、OpenAI 為內容理解引擎、Notion 為筆記發佈端、SQLite 為學習紀錄儲存層的文件學習系統。它會把 PDF、DOCX、TXT 或 Markdown 轉成分章學習筆記，並延伸成 Quiz、Flash Card、弱點追蹤與學習儀表板。

## 核心設計原則

- 解析、AI、匯出、資料庫與畫面分層，避免單一檔案承擔全部責任。
- AI 回傳先經 Pydantic 驗證，再交給下游使用。
- 視覺分析與詳細筆記使用快取，降低重複 API 成本。
- Notion 匯出使用狀態檔，可在失敗後續跑。
- Quiz 與 Flash Card 同步採非破壞性合併，保留既有練習紀錄。
- SQLite 使用 UUID 字串主鍵，讓各層 ID 型別一致。
- 資料管理頁提供診斷、清理與快取回填，讓異常可被觀察和修復。

## 目前版本界線

目前完成到 V2.5，定位是單機 Windows 學習應用程式。它適合個人使用，也能作為正式雲端版的原型；尚未包含多人帳號、雲端資料隔離、背景工作佇列與集中式物件儲存。
