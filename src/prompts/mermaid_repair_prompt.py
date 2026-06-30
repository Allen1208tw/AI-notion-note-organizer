def build_mermaid_repair_prompt(
    document_summary: str,
    current_mermaid: str,
    error_reason: str,
) -> str:
    """建立 Mermaid 修正 Prompt。"""

    return f"""
請根據文件摘要，重新產生一份正確、聚焦主題的 Mermaid 圖表。

你必須只輸出 Mermaid 原始碼，不可輸出 JSON、說明文字或 Markdown Code Fence。

文件摘要：
{document_summary}

目前 Mermaid：
{current_mermaid}

需要修正的原因：
{error_reason}

規則：
1. 第一行必須直接以 flowchart TD 開始。
2. 不可使用 Emoji。
3. 不可使用 ```mermaid 或任何 Markdown Code Fence。
4. 節點數量控制在 8 到 12 個以內。
5. 節點文字不可包含條列編號、序號、項目符號。
6. 節點文字盡量控制在 12 個中文字內。
7. 圖表必須呈現文件最核心的知識結構、學習路徑或工作流程。
8. 不可只依照文章段落順序連線。
9. 政策背景、行政資訊、補助資訊、活動資訊只能是補充，不可取代主流程。
10. 如果是課程文件，優先畫出：
   基礎能力 → 核心技術 → 進階主題 → 專題實作 → 就業成果。
"""