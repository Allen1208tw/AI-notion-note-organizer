import re


ALLOWED_DIAGRAM_TYPES = (
    "flowchart TD",
    "flowchart LR",
    "mindmap",
    "sequenceDiagram",
)


MERMAID_LABEL_TRANSLATION = str.maketrans(
    {
        "<": "＜",
        ">": "＞",
        "{": "｛",
        "}": "｝",
        "[": "［",
        "]": "］",
        "|": "｜",
        '"': "＂",
        "'": "＇",
        "&": "＆",
        "#": "＃",
        "=": "＝",
        ":": "：",
        ";": "；",
    }
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


def _sanitize_label_text(label: str) -> str:
    """將 Mermaid 節點標籤中的特殊字元改成安全顯示字元。"""

    cleaned = str(label or "").strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.translate(MERMAID_LABEL_TRANSLATION)


def sanitize_mermaid_for_notion(mermaid_text: str) -> str:
    """
    將 AI 產生的 Mermaid 轉成比較適合 Notion 渲染的版本。

    HTML/CSS 教材常包含 <div>、{ }、|、#、: 等符號。這些符號若
    直接出現在 Mermaid node label，容易被解析器當成語法。這裡只
    處理節點顯示文字，不改箭頭與圖表結構。
    """

    text = str(mermaid_text or "").strip()

    if text.startswith("```"):
        text = re.sub(
            r"^```(?:mermaid)?\s*",
            "",
            text,
            flags=re.IGNORECASE,
        )
        text = re.sub(r"\s*```$", "", text)

    sanitized_lines = []

    for raw_line in text.splitlines():
        line = raw_line.rstrip()

        # A[<div>] / A(Selector: #id) / A{display:block}
        def replace_bracket_label(match: re.Match) -> str:
            prefix = match.group(1)
            opener = match.group(2)
            label = match.group(3)
            closer = match.group(4)
            return f"{prefix}{opener}{_sanitize_label_text(label)}{closer}"

        line = re.sub(
            r"([A-Za-z0-9_]+)([\[\(\{])([^\]\)\}]+)([\]\)\}])",
            replace_bracket_label,
            line,
        )

        # A["<input type='text'>"] / A['a|b']
        def replace_quoted_label(match: re.Match) -> str:
            prefix = match.group(1)
            quote = match.group(2)
            label = match.group(3)
            return f"{prefix}{quote}{_sanitize_label_text(label)}{quote}"

        line = re.sub(
            r"([A-Za-z0-9_]+)([\"'])(.+?)\2",
            replace_quoted_label,
            line,
        )

        # mindmap 通常以縮排行表示節點，直接安全化非第一行文字。
        if (
            sanitized_lines
            and sanitized_lines[0].strip().startswith("mindmap")
            and line.strip()
            and not re.match(r"^\s*(root|id)\s*\(", line)
        ):
            indent = line[: len(line) - len(line.lstrip())]
            line = indent + _sanitize_label_text(line.strip())

        sanitized_lines.append(line)

    return "\n".join(sanitized_lines).strip()


def validate_mermaid(mermaid_text: str) -> tuple[bool, str]:
    """驗證 Mermaid 是否符合 Notion 相容規則。"""

    if not mermaid_text or not mermaid_text.strip():
        return False, "Mermaid 圖表內容是空的。"

    cleaned_text = sanitize_mermaid_for_notion(mermaid_text)

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
