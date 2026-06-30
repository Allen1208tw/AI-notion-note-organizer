# AI Notion Note Organizer

一個使用 Python、Streamlit、OpenAI API 與 Notion API 製作的文件整理工具。

使用者可上傳 PDF、DOCX、TXT 或 Markdown 文件，系統會自動解析內容、清理文字、分段分析，並產生結構化筆記、Mermaid 圖表、Quiz、Flash Cards，最後可匯出 Markdown／JSON，或直接建立 Notion 筆記頁面。

---

## 功能特色

* 支援 PDF、DOCX、TXT、Markdown 文件上傳
* 自動驗證檔案格式與大小
* 自動解析、清理與分段文字內容
* 使用 OpenAI API 分段分析與整合文件內容
* 產生文件摘要與重點整理
* 產生 Mermaid 知識流程圖
* 自動產生 Quiz 與 Flash Cards
* 匯出 Notion Markdown 檔案
* 匯出 JSON 結構化資料
* 直接建立 Notion 筆記頁面
* Quiz 與 Flash Cards 會在 Notion 中建立為可收合的 Toggle 區塊

---

## 系統流程

```text
上傳文件
→ 驗證檔案
→ 解析文字
→ 清理文字
→ Chunk 分段
→ AI 分段分析
→ AI 整合完整筆記
→ 摘要 / 重點 / Mermaid / Quiz / Flash Cards
→ Markdown / JSON 匯出
→ 建立 Notion 頁面
```

---

## 專案結構

```text
ai_notion-note-organizer/
├── app.py
├── requirements.txt
├── .env
├── .env.example
├── README.md
│
├── docs/
│   ├── 01_project_overview.md
│   ├── 02_system_architecture.md
│   ├── 03_project_structure.md
│   ├── 04_tech_stack.md
│   ├── 05_database_design.md
│   ├── 06_data_flow.md
│   ├── 07_prompt_design.md
│   ├── 08_api_design.md
│   ├── 09_ui_ux_design.md
│   ├── 10_development_roadmap.md
│   └── 11_sprint_planning.md
│
├── src/
│   ├── config/
│   ├── exporters/
│   ├── models/
│   ├── parsers/
│   ├── processors/
│   ├── prompts/
│   ├── services/
│   ├── validators/
│   └── utils/
│
├── outputs/
├── sample_files/
└── tests/
```

---

## 技術棧

| 類型        | 技術                  |
| --------- | ------------------- |
| 前端介面      | Streamlit           |
| 程式語言      | Python              |
| AI 分析     | OpenAI API          |
| 文件解析      | PyMuPDF、python-docx |
| 資料模型驗證    | Pydantic            |
| 環境變數管理    | python-dotenv       |
| Notion 整合 | notion-client       |
| 筆記匯出      | Markdown、JSON       |
| 視覺化       | Mermaid             |

---

## 安裝方式

### 1. 複製專案

```powershell
git clone <your-repository-url>
cd ai_notion-note-organizer
```

### 2. 建立虛擬環境

```powershell
python -m venv .venv
```

### 3. 啟動虛擬環境

```powershell
.venv\Scripts\Activate.ps1
```

### 4. 安裝套件

```powershell
pip install -r requirements.txt
```

---

## 環境變數設定

在專案根目錄建立 `.env` 檔案：

```text
OPENAI_API_KEY=你的_OpenAI_API_Key

OPENAI_CHUNK_MODEL=gpt-5-mini
OPENAI_MERGE_MODEL=gpt-5

MAX_FILE_SIZE_MB=10
CHUNK_SIZE=6000
CHUNK_OVERLAP=500

NOTION_API_KEY=你的_Notion_Integration_Token
NOTION_PARENT_PAGE_ID=你的_Notion_父頁面_ID
```

請勿將 `.env` 上傳到 GitHub。

---

## 啟動專案

```powershell
streamlit run app.py
```

啟動後，終端機會顯示本機網址，通常是：

```text
http://localhost:8501
```

---

## 使用流程

1. 開啟網頁介面
2. 上傳 PDF、DOCX、TXT 或 Markdown 文件
3. 點擊「開始分析」
4. 確認文字解析與分段結果
5. 點擊「分析整份文件」
6. 查看摘要、重點、Mermaid、Quiz、Flash Cards
7. 選擇下載 Markdown 或 JSON
8. 或點擊「建立 Notion 筆記頁面」

---

## Notion 整合說明

系統會在指定的 Notion 父頁面下建立新的子頁面。

建立完成後：

* 文件摘要會以段落顯示
* 重點整理會以項目清單顯示
* Mermaid 會以程式碼區塊保存
* Quiz 題目會以 Toggle 區塊顯示
* Flash Cards 會以 Toggle 區塊顯示

使用者可以點擊 Quiz 題目查看答案，或點擊 Flash Card 正面查看背面內容。

---

## 支援格式

| 格式       | 支援狀態      |
| -------- | --------- |
| PDF      | 支援文字型 PDF |
| DOCX     | 支援        |
| TXT      | 支援        |
| Markdown | 支援        |

目前不支援掃描型圖片 PDF 的 OCR 辨識。

---

## 已知限制

* 長文件會因 Chunk 數量增加而提升分析時間與 API 成本
* Mermaid 目前以原始碼形式寫入 Notion，不會自動轉成 Notion 視覺化圖表
* AI 產生內容仍可能需要人工檢查
* PDF 若沒有文字層，系統無法直接解析內容
* Notion 頁面必須先授權給 Integration，否則無法建立筆記

---

## V1 功能完成狀態

* [x] 文件上傳與驗證
* [x] PDF / DOCX / TXT / Markdown 解析
* [x] 文字清理與分段
* [x] OpenAI 分段分析
* [x] 文件整合摘要
* [x] Mermaid 圖表生成
* [x] Quiz 與 Flash Cards 生成
* [x] Markdown 匯出
* [x] JSON 匯出
* [x] Notion API 建立頁面
* [x] Notion Toggle Quiz / Flash Cards

---

## V1.5 規劃

* 章節化學習筆記生成
* 每章白話講解
* 自動產生案例與延伸說明
* 常見錯誤與易混淆觀念
* 每章 Quiz 與 Flash Cards
* 更進階的視覺化圖表
* 手動優化摘要與 Mermaid
* 更完整的錯誤提示與測試覆蓋

---

## 作者

AI Notion Note Organizer
Python AI 應用工程師學習專案
