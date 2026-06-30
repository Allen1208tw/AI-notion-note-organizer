import re


ALLOWED_DIAGRAM_TYPES = (
    "flowchart TD",
    "flowchart LR",
    "mindmap",
    "sequenceDiagram",
)


def contains_emoji(text: str) -> bool:
    """檢查文字是否包含 Emoji。"""

    emoji_pattern = re.compile(
        "["
        "\U0001F300-\U0001F5FF"
        "\U0001F600-\U0001F64F"
        "\U0001F680-\U0001F6FF"
        "\U0001F700-\U0001F77F"
        "\U0001F780-\U0001F7FF"
        "\U0001F800-\U0001F8FF"
        "\U0001F900-\U0001F9FF"
        "\U0001FA00-\U0001FA6F"
        "\U0001FA70-\U0001FAFF"
        "\U00002700-\U000027BF"
        "]+",
        flags=re.UNICODE,
    )

    return bool(emoji_pattern.search(text))


def validate_mermaid(mermaid_text: str) -> tuple[bool, str]:
    """驗證 Mermaid 是否符合 Notion 相容規則。"""

    if not mermaid_text or not mermaid_text.strip():
        return False, "Mermaid 圖表內容是空的。"

    cleaned_text = mermaid_text.strip()

    if "```" in cleaned_text:
        return False, "Mermaid 不可包含 Markdown Code Fence。"

    if contains_emoji(cleaned_text):
        return False, "Mermaid 圖表內容不可包含 Emoji。"

    first_line = cleaned_text.splitlines()[0].strip()

    if not first_line.startswith(ALLOWED_DIAGRAM_TYPES):
        return (
            False,
            "Mermaid 第一行必須以 flowchart TD、flowchart LR、"
            "mindmap 或 sequenceDiagram 開始。",
        )

    return True, ""