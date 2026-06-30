def build_mermaid_quality_prompt(
    document_summary: str,
    mermaid: str,
) -> str:
    """建立 Mermaid 語意品質檢查 Prompt。"""

    return f"""
請評估以下 Mermaid 圖表是否真正呈現文件的核心主題。

你必須只輸出合法 JSON，不可輸出其他文字。

文件摘要：
{document_summary}

Mermaid 圖表：
{mermaid}

請依照以下格式輸出：

{{
  "is_focused": true,
  "reason": "簡短說明",
  "should_repair": false
}}

判斷規則：
1. Mermaid 主流程必須呈現文件最重要的知識結構、學習路徑或工作流程。
2. 不可只把文件段落依文章順序串起來。
3. 政策、補助、行政資訊、活動安排、講師資訊等，不能取代文件的核心主題。
4. 若文件是課程介紹，圖表應優先呈現：
   基礎能力 → 核心技術 → 進階主題 → 專題實作 → 就業成果。
5. 若 Mermaid 主流程偏離核心主題，請設定：
   "is_focused": false
   "should_repair": true
6. 若 Mermaid 已聚焦且關係合理，請設定：
   "is_focused": true
   "should_repair": false
7. reason 請使用繁體中文，20 至 50 字。
"""