# AI Notion Note Organizer

## Prompt Design

### 1. 目的

本文件定義 AI Notion Note Organizer 使用 OpenAI API 時的 Prompt 設計規則。

目標是讓 AI 能穩定產出：

* 文件摘要
* 重點整理
* Mermaid 圖表
* Quiz
* Flash Card
* Notion 相容 Markdown 所需資料

---

### 2. 全域輸出規則

* 使用繁體中文回答。
* 一般文字內容可適量使用 Emoji。
* Mermaid 圖表內容不可使用 Emoji。
* Markdown 程式碼區塊不可使用 Emoji。
* Mermaid 不可包含 Markdown Code Fence。
* Mermaid 第一行必須直接從 `flowchart TD`、`flowchart LR`、`mindmap` 或 `sequenceDiagram` 開始。
* Mermaid 節點文字需簡短明確。
* 不可加入與文件無關的內容。
* 若文件資訊不足，必須明確標示資訊不足，不可自行捏造內容。

---

### 3. AI 輸出內容

AI 最終需產出以下欄位：

```text
summary
key_points
mermaid
quiz
flashcards
```

---

### 4. Chunk 分析規則

長文件會先切成多個 Chunk。

每個 Chunk 需要整理：

* 段落摘要
* 重要觀念
* 關鍵術語
* Quiz 題目素材
* Flash Card 問答素材

完成所有 Chunk 分析後，再由合併 Prompt 統整成完整筆記。

---

### 5. 後續規劃

後續將補上：

* System Prompt
* Chunk Prompt
* Merge Prompt
* JSON Schema
* Mermaid Repair Prompt
* JSON Repair Prompt
* API 錯誤與降級策略
