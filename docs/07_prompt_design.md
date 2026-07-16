# Prompt 與結構化輸出設計

## Prompt 分層

提示詞放在 `src/prompts/`，依任務拆分：全域角色、Chunk 分析、多 Chunk 合併、章節學習筆記、摘要品質、Mermaid 品質與修復。Prompt 與 Service 分離，內容規格可以獨立迭代，也不會讓 UI 或資料庫程式混入大型模板。

## 兩階段文件分析

長文件可能超過模型上下文，也容易忽略中後段。專案採 Map-Reduce 概念：

```text
文件 -> Chunks -> 各自結構化分析 -> 合併 Prompt -> 整份結果
```

Chunk Prompt 忠於局部內容；Merge Prompt 負責跨區塊去重、排序、統一術語和全局摘要。

## 詳細章節 Prompt

輸入包含章節編號、描述性標題、章節文字及可選的 PDF 圖片分析。輸出對應 `ChapterLearningNote`：學習目標、摘要、白話講解、核心重點、術語、規則、程式碼、錯誤、子章節、Callout、比較表、圖片解讀、練習建議、Mermaid、Quiz 與 Flash Card。

## 三方契約

新增 AI 欄位時必須同步修改：

1. Prompt：要求模型產生欄位。
2. Pydantic Model：定義欄位型別和巢狀結構。
3. Renderer：決定 Streamlit、Markdown 或 Notion 如何呈現。

只改 Prompt，Pydantic 可能拒絕資料；只改 Model，AI 不一定產生；只改 Renderer，來源欄位可能不存在。

## 結構化輸出防護

服務取得回應後會移除可能的 Code Fence、解析 JSON、以 Pydantic 驗證，失敗時帶更明確格式要求重試。超過次數才向上回報。這比用字串切割找答案可靠，因為下游需要穩定欄位建立 Notion Blocks 和資料庫紀錄。

## 降低幻覺

- 要求只依提供內容回答。
- 每個 Chunk 有明確來源邊界。
- Quiz 答案必須能由章節內容支持。
- 圖片分析作為補充上下文，不假裝是原文。
- 資訊不足要明示，不自行補造。

Pydantic 保障結構，不保障事實；內容品質仍需 Prompt 約束、模型能力和人工抽查。

## Quiz 與 Flash Card

Quiz 至少需要問題和標準答案，Flash Card 至少需要正反面；缺核心欄位的項目不寫入 SQLite。同步 identity 同時使用問題與答案，避免相似問題但答案不同時被錯誤合併。

## Mermaid

生成、品質判斷、修復與驗證分開。Mermaid 失敗不應阻止摘要、Quiz 或 Notion 其他內容完成，這叫做功能降級而非整批失敗。

## Prompt 回歸方法

每次調整使用固定樣本比較：JSON 成功率、欄位完整率、標題品質、題目可回答性、重複率、Token 成本和處理時間。不能只憑一次輸出更漂亮就替換正式 Prompt。

## 常見技術追問

**為什麼不讓 AI 直接輸出 Notion Blocks？**

這會讓內容與 Notion API 強耦合，Block 錯誤也難驗證。先產生領域 Model，再由確定性的 Python Builder 轉換，較容易測試、重用與修復。

**Pydantic 能完全避免 AI 錯誤嗎？**

不能。它保證型別和結構，不保證內容真實性。
