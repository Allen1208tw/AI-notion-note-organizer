# AI Notion 期中專題簡報 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 產出一份 10–15 分鐘、深色科技風、含真實介面截圖與漸進揭露效果的 AI Notion 期中專題 PowerPoint。

**Architecture:** 使用 `@oai/artifact-tool` 建立 16:9 可編輯簡報；以 13 個內容段落加少量重複關鍵畫面呈現動畫式漸進揭露。真實 Streamlit 與私人 Notion 畫面以 PNG 嵌入，API Key 與 Token 不得出現在任何截圖。簡報匯出後以 Open XML 加入一致的 Fade 轉場，再以靜態渲染、版面檢查與轉場結構檢查完成驗證。

**Tech Stack:** JavaScript ES modules、`@oai/artifact-tool`、JSZip、PowerPoint Open XML、Streamlit、Codex Browser／Chrome、Python 簡報驗證工具。

## Global Constraints

- 交付物只有可編輯 PowerPoint，不產出 PDF。
- 投影片比例固定為 16:9，畫布使用 1280 × 720。
- 觀眾修過 AI 應用工程師課程，具備 Python、API、Prompt 與 JSON 基礎。
- 主風格為深色科技風；青藍代表資料流、綠色代表成功、紫色代表 AI、橘紅代表 BUG。
- 技術詞彙採「白話名稱＋正式名稱」，保留 Chunk、overlap、Map-Reduce、structured output、Pydantic schema validation 與背景工作。
- 不放大段原始碼；JSON 或 Pydantic Model 片段只保留理解所需內容。
- 使用真實程式與私人 Notion 畫面，但 API Key、Token 與其他憑證不得出現。
- 所有外部素材與非顯然技術主張都要在 speaker notes 的 `[Sources]` 區塊記錄來源。
- 所有投影片必須逐頁渲染、逐頁檢查，且 `slides_test.py` 必須通過。

---

### Task 1: 準備真實介面素材與來源紀錄

**Files:**
- Create: `outputs/ai_notion_midterm_build/assets/app-upload.png`
- Create: `outputs/ai_notion_midterm_build/assets/app-learning.png`
- Create: `outputs/ai_notion_midterm_build/assets/notion-result.png`
- Create: `outputs/ai_notion_midterm_build/source-notes.txt`

**Interfaces:**
- Consumes: 現有 Streamlit 專案、私人 Notion 頁面、`docs/` 技術文件。
- Produces: 三張不含憑證的 PNG，以及供簡報 speaker notes 使用的來源清單。

- [ ] **Step 1: 建立素材目錄並啟動本機程式**

Run:

```powershell
New-Item -ItemType Directory -Force outputs\ai_notion_midterm_build\assets
$python = (Resolve-Path '.\.venv\Scripts\python.exe').Path
$stdout = (Resolve-Path 'outputs\ai_notion_midterm_build').Path + '\streamlit.log'
$stderr = (Resolve-Path 'outputs\ai_notion_midterm_build').Path + '\streamlit-error.log'
Start-Process -FilePath $python `
  -ArgumentList @('-m','streamlit','run','AI_Notion_筆記整理器.py','--server.headless','true','--server.port','8501') `
  -WindowStyle Hidden -RedirectStandardOutput $stdout -RedirectStandardError $stderr
```

Expected: Streamlit 顯示本機 URL，首頁可正常載入。

- [ ] **Step 2: 擷取上傳與學習功能畫面**

使用 Browser 控制本機頁面，分別擷取：

1. 文件管理／上傳畫面，保留檔案與操作區。
2. Quiz 或 Flash Card 畫面，保留題目與作答區。

儲存為 `app-upload.png` 與 `app-learning.png`。不要打開設定頁，不要讓 `.env`、API Key 或 Token 出現在畫面中。

- [ ] **Step 3: 擷取私人 Notion 成果頁**

使用既有 Chrome 登入狀態開啟私人 Notion 成果頁，只擷取筆記標題、章節、Callout／Toggle／Quiz 等代表區域。裁掉瀏覽器帳號資訊與無關側欄，儲存為 `notion-result.png`。

- [ ] **Step 4: 視覺檢查三張素材**

逐張以原始尺寸檢查：文字可讀、沒有憑證、沒有桌面通知、沒有多餘黑邊。若任一素材不符合，重新擷取，不使用模糊遮罩補救。

- [ ] **Step 5: 寫入來源紀錄**

`source-notes.txt` 必須列出：

```text
Local project sources:
- docs/01_project_overview.md
- docs/02_system_architecture.md
- docs/04_tech_stack.md
- docs/06_data_flow.md
- docs/07_prompt_design.md
- docs/13_demo_and_technical_qa.md
- src/processors/text_cleaner.py
- src/processors/text_chunker.py
- src/processors/chapter_detector.py
- src/models/analysis_models.py
- src/services/background_job_service.py

Captured assets:
- app-upload.png — local Streamlit document management page
- app-learning.png — local Quiz or Flash Card page
- notion-result.png — private Notion output page, authorized by user
```

### Task 2: 建立簡報工作區與內容骨架

**Files:**
- Create: `outputs/ai_notion_midterm_build/build_midterm_deck.mjs`
- Create: `outputs/ai_notion_midterm_build/package.json`
- Create: `outputs/ai_notion_midterm_build/rendered/`

**Interfaces:**
- Consumes: Task 1 PNG 素材與已核准的設計規格。
- Produces: 使用 `@oai/artifact-tool` 建立的初版 PPTX、每頁 PNG、layout JSON 與 montage。

- [ ] **Step 1: 初始化 Artifact Tool 工作區**

Run:

```powershell
& 'C:\Users\student\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe' `
  'C:\Users\student\.codex\plugins\cache\openai-primary-runtime\presentations\26.730.11710\skills\presentations\container_tools\setup_artifact_tool_workspace.mjs' `
  --workspace 'C:\ai_notion\ai_notion-note-organizer\outputs\ai_notion_midterm_build'
```

Expected: 工作區可解析 `@oai/artifact-tool`。

- [ ] **Step 2: 建立視覺 token 與共用 helper**

在 `build_midterm_deck.mjs` 定義：

```js
const COLORS = {
  bg: "#0B1220",
  panel: "#111D31",
  cyan: "#5AD7FF",
  green: "#6FE7B2",
  purple: "#A78BFA",
  warning: "#FF8A65",
  text: "#F4F7FC",
  muted: "#A8B4C8",
};

function addTitle(slide, title, eyebrow) { /* 35pt 以上、單行不換行 */ }
function addBugCallout(slide, expected, actual, fix) { /* 原本／實際／修正 */ }
function setSources(slide, sources) {
  slide.speakerNotes.textFrame.setText(`[Sources]\n${sources.map(x => `- ${x}`).join("\n")}\n[/Sources]`);
}
```

共用 helper 只負責標題、頁碼、BUG 提示與來源；各頁仍維持單一主視覺，不建立密集 UI 卡片網格。

- [ ] **Step 3: 建立 13 個內容段落與漸進揭露頁**

依序建立：封面、問題、核心目標、成果預覽、技術堆疊、架構揭露 1／2、文件旅程揭露 1／2、清洗與章節 BUG、Chunk／overlap 與 BUG、Prompt、Pydantic 揭露 1／2、發布保存與 BUG、總結。

實際投影片數預計 16–17 頁，但內容仍維持 13 個段落；重複頁只改變新揭露元素，既有元素位置不得移動。

- [ ] **Step 4: 使用真實截圖與文件 X 光示意**

成果預覽頁嵌入三張 Task 1 素材。清洗頁並排顯示原始／清洗後文字；Chunk 頁用三個閱讀包及共享色帶表示 overlap；Prompt 頁用短 structured output JSON；Pydantic 頁用精簡 Model 與錯誤回傳對照。

- [ ] **Step 5: 匯出初版與檢查資料**

Builder 必須輸出：

```text
outputs/AI_Notion_期中專題發表_深色科技風.pptx
outputs/ai_notion_midterm_build/rendered/slide-01.png ...
outputs/ai_notion_midterm_build/rendered/slide-01.layout.json ...
outputs/ai_notion_midterm_build/rendered/contact-sheet.webp
```

### Task 3: 加入 PowerPoint Fade 轉場並驗證

**Files:**
- Create: `outputs/ai_notion_midterm_build/add_fade_transitions.mjs`
- Create: `outputs/ai_notion_midterm_build/verify_transitions.mjs`
- Modify: `outputs/AI_Notion_期中專題發表_深色科技風.pptx`

**Interfaces:**
- Consumes: Task 2 匯出的 PPTX。
- Produces: 每張投影片都有 Fast Fade 的最終 PPTX，以及可機器檢查的轉場報告。

- [ ] **Step 1: 寫轉場結構測試並確認初版失敗**

`verify_transitions.mjs` 使用 JSZip 讀取 `ppt/slides/slide*.xml`，要求每張投影片都有：

```xml
<p:transition spd="fast"><p:fade/></p:transition>
```

Run:

```powershell
node outputs\ai_notion_midterm_build\verify_transitions.mjs outputs\AI_Notion_期中專題發表_深色科技風.pptx
```

Expected: FAIL，列出尚未包含 transition 的 slide XML。

- [ ] **Step 2: 實作 Open XML 轉場後處理**

`add_fade_transitions.mjs` 使用 JSZip 解壓 PPTX，將 transition 插入 `<p:cSld>` 之前，保留其他 XML 與 ZIP 項目：

```js
const transition = '<p:transition spd="fast"><p:fade/></p:transition>';
xml = xml.includes('<p:transition')
  ? xml
  : xml.replace('<p:cSld', `${transition}<p:cSld`);
```

輸出至暫存檔後，再以同一路徑覆蓋最終 PPTX。

- [ ] **Step 3: 執行後處理並確認轉場測試通過**

Run:

```powershell
node outputs\ai_notion_midterm_build\add_fade_transitions.mjs outputs\AI_Notion_期中專題發表_深色科技風.pptx
node outputs\ai_notion_midterm_build\verify_transitions.mjs outputs\AI_Notion_期中專題發表_深色科技風.pptx
```

Expected: PASS，回報所有 slide XML 均含 Fast Fade。

### Task 4: 渲染、逐頁 QA 與最終交付

**Files:**
- Modify: `outputs/ai_notion_midterm_build/build_midterm_deck.mjs`
- Modify: `outputs/AI_Notion_期中專題發表_深色科技風.pptx`
- Create: `outputs/ai_notion_midterm_build/qa-ledger.txt`

**Interfaces:**
- Consumes: 含轉場的最終 PPTX。
- Produces: 通過視覺、版面、內容與轉場檢查的唯一最終交付檔。

- [ ] **Step 1: 執行版面溢位檢查**

Run:

```powershell
& 'C:\Users\student\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' `
  'C:\Users\student\.codex\plugins\cache\openai-primary-runtime\presentations\26.730.11710\skills\presentations\container_tools\slides_test.py' `
  'C:\ai_notion\ai_notion-note-organizer\outputs\AI_Notion_期中專題發表_深色科技風.pptx'
```

Expected: `Test passed. No overflow detected.`

- [ ] **Step 2: 重新渲染全部投影片**

Run:

```powershell
& 'C:\Users\student\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' `
  'C:\Users\student\.codex\plugins\cache\openai-primary-runtime\presentations\26.730.11710\skills\presentations\container_tools\render_slides.py' `
  'C:\ai_notion\ai_notion-note-organizer\outputs\AI_Notion_期中專題發表_深色科技風.pptx'
```

- [ ] **Step 3: 逐頁視覺檢查並修正**

逐頁以原始尺寸檢查：標題不換行、截圖清晰、BUG callout 不搶主視覺、架構箭頭位於節點後方、揭露頁元素位置一致、頁碼與 footer 一致。任何問題都回到 builder 修正、重新匯出、重新加 transition，再重跑測試。

- [ ] **Step 4: 建立接觸表並檢查整體節奏**

以 `create_montage.py` 建立 contact sheet，確認深色科技風一致、相鄰頁輪廓有變化、沒有連續多頁過度密集。

- [ ] **Step 5: 完成 QA 紀錄與最終驗證**

`qa-ledger.txt` 記錄：投影片數、逐頁檢查完成、`slides_test.py` 結果、transition 檢查結果、三張截圖的敏感資訊檢查結果。最後再次確認最終 PPTX 存在且可讀。
