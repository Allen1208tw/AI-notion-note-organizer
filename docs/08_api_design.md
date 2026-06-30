# AI Notion Note Organizer

## API Design

### 1. OpenAI API 用途

V1 MVP 使用 OpenAI API 分析文件內容，產出摘要、重點整理、Mermaid 圖表、Quiz 與 Flash Card。

---

### 2. API 呼叫原則

* OpenAI API Key 只從 `.env` 讀取。
* API Key 不可寫死在程式碼中。
* 所有 OpenAI 呼叫集中於 `src/services/openai_service.py`。
* UI 不直接呼叫 OpenAI API。
* API 發生錯誤時，需回傳可理解的錯誤訊息。
* 後續分析流程會使用固定 JSON 結構驗證回傳內容。

---

### 3. V1 呼叫流程

```text
Streamlit UI
→ analysis_service.py
→ openai_service.py
→ OpenAI API
→ AI Response
→ Result Validator
```
