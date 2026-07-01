from src.models.chapter_models import ChapterLearningNote


def _format_subsections(subsections: list[dict] | None) -> str:
    """將子章節資料整理成可放入 Prompt 的文字。"""

    if not subsections:
        return "此主章節沒有偵測到明確子章節。"

    subsection_blocks = []

    for subsection in subsections:
        title = subsection.get("title", "未命名子章節")
        content = subsection.get("content", "").strip()

        subsection_blocks.append(
            f"""
子章節標題：
{title}

子章節原始內容：
{content}
""".strip()
        )

    return "\n\n".join(subsection_blocks)


def _format_visual_context(
    visual_context: list[dict] | None,
) -> str:
    """
    將 PDF 圖片或頁面視覺分析結果整理成 Prompt 內容。

    visual_context 預期格式：
    [
        {
            "page_number": 10,
            "description": "VS Code 開啟工作區畫面...",
        }
    ]
    ]
    """

    if not visual_context:
        return (
            "目前沒有提供圖片分析資料。"
            "請不要捏造圖片內容，image_insights 可回傳空陣列。"
        )

    visual_blocks = []

    for item in visual_context:
        page_number = item.get("page_number", "未知")
        description = item.get("description", "").strip()

        if not description:
            continue

        visual_blocks.append(
            f"""
PDF 頁碼：{page_number}

圖片或畫面描述：
{description}
""".strip()
        )

    if not visual_blocks:
        return (
            "目前沒有可用圖片分析資料。"
            "請不要捏造圖片內容，image_insights 可回傳空陣列。"
        )

    return "\n\n".join(visual_blocks)


def build_chapter_prompt(
    chapter_title: str,
    chapter_content: str,
    subsections: list[dict] | None = None,
    visual_context: list[dict] | None = None,
) -> str:
    """
    建立 V1.5 詳細學習筆記 Prompt。

    chapter_title:
        主章節名稱，例如 Module 17｜CSS 樣式屬性

    chapter_content:
        該主章節完整文字內容

    subsections:
        偵測到的子章節資料，例如 17-1、17-2、17-3

    visual_context:
        PDF 圖片、流程圖、操作截圖的視覺分析結果。
        目前可不傳，後續接上圖片分析功能後使用。
    """

    subsection_text = _format_subsections(subsections)
    visual_text = _format_visual_context(visual_context)

    schema = ChapterLearningNote.model_json_schema()

    return f"""
你是一位擅長 HTML、CSS、程式設計教學、初學者引導與 Notion 學習筆記整理的 AI 助教。

請根據提供的主章節、子章節與圖片輔助資料，產生一份完整、好讀、可複習的「詳細學習筆記」。

主章節名稱：
{chapter_title}

主章節原始內容：
{chapter_content}

子章節資訊：
{subsection_text}

圖片或視覺輔助資訊：
{visual_text}

請務必遵守以下規則：

1. 一律使用繁體中文。
2. 內容要以初學者能理解的教學方式撰寫，不可只做短摘要。
3. 必須保留原文中的重要概念、HTML 標籤、CSS 屬性、程式語法、數字、規則、限制與注意事項。
4. 不可捏造原始內容沒有提到的技術細節。
5. 若圖片輔助資訊不存在，image_insights 必須回傳空陣列，不可自行虛構圖片內容。
6. chapter_summary 要濃縮說明本章在教什麼，以及學完後能做到什麼。
7. plain_explanation 必須使用白話、具體、有邏輯的方式解釋概念。
8. learning_objectives 至少 3 點；內容不足時可減少。
9. key_points 優先保留具體規則與可操作知識，避免空泛描述。
10. important_terms 格式建議為：
    "術語：白話解釋"
11. syntax_rules 用來整理 HTML、CSS、JavaScript 語法規則、屬性用途、限制與注意事項。
12. code_examples 只能使用原文已出現的程式碼，或依原文可直接合理整理出的短範例。
13. code_examples 的 explanation 必須解釋：
    - 程式碼用途
    - 關鍵語法
    - 初學者需要注意的地方
14. common_mistakes 必須以初學者容易犯錯或混淆的觀念為主。
15. subsections 必須依照提供的子章節整理，盡量不要遺漏。
16. callout_notes 至少產生 2 個，優先使用：
    - 💡 核心觀念
    - ⚠️ 容易混淆
    - 📌 必記規則
    - ✅ 實作提醒
17. callout_notes 的 tone 只能使用：
    - info
    - warning
    - success
    - tip
18. comparison_tables 只在確實適合比較時產生。
    例如：
    - display 與 visibility
    - class 與 id
    - inline、embedding、linking
19. comparison_tables 的 headers 至少 2 欄。
20. comparison_tables 每列 rows 的欄位數必須與 headers 完全一致。
21. practice_tips 要提供可以直接執行的小練習。
22. practice_tips 的 expected_result 要說明完成後應看到或理解什麼。
23. image_insights 只能根據提供的圖片或視覺輔助資料生成。
24. Mermaid 圖只能使用 Mermaid 原始語法：
    - 不可使用 Markdown Code Fence。
    - 不可使用 Emoji。
    - 第一行只能使用 flowchart TD、flowchart LR、mindmap 或 sequenceDiagram。
    - 節點文字不超過 12 個中文字。
    - 聚焦本章學習概念與關係。
25. quiz 至少建立 5 題；內容不足時可減少。
26. quiz 的 explanation 要說明答案為什麼正確。
27. flashcards 至少建立 5 張；內容不足時可減少。
28. 回覆只能輸出完整、合法 JSON。
29. 不可輸出 Markdown、Code Fence、註解、前言或任何額外文字。
30. 所有欄位都必須符合以下 JSON Schema。

JSON Schema：
{schema}
"""