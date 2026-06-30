def build_summary_quality_prompt(
    document_summary: str,
    chunk_results: list[dict],
) -> str:
    """建立摘要完整度檢查 Prompt。"""

    return f"""
請檢查以下「完整文件摘要」是否有涵蓋所有重要資訊。

你必須只輸出合法 JSON，不可輸出其他文字。

完整文件摘要：
{document_summary}

各段分析結果：
{chunk_results}

請依照以下格式輸出：

{{
  "is_complete": true,
  "missing_topics": [],
  "reason": "簡短說明",
  "should_repair": false
}}

判斷規則：
1. 摘要必須涵蓋各段落中重複出現或明顯重要的主題。
2. 不可只整理前半段內容。
3. 若文件包含目標、流程、技術內容、時數、限制條件、活動安排、人物、日期、數據或結論，應視重要性納入摘要。
4. 不可因為摘要簡短而遺漏核心段落。
5. 若摘要已完整涵蓋核心內容：
   - "is_complete": true
   - "should_repair": false
6. 若摘要漏掉重要主題：
   - "is_complete": false
   - "should_repair": true
7. missing_topics 請列出缺漏主題，例如：
   ["課程總時數", "後段就業媒合安排"]
8. reason 請使用繁體中文，20 至 50 字。
"""