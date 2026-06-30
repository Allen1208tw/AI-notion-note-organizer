from datetime import datetime

from src.models.analysis_models import AnalysisResult
from src.validators.mermaid_validator import validate_mermaid


def build_markdown(
    document_name: str,
    analysis_result: AnalysisResult,
) -> str:
    """將分析結果組裝成 Notion 相容 Markdown。"""

    lines = []

    lines.append(f"# {document_name}")
    lines.append("")
    lines.append("> AI Notion Note Organizer 自動整理筆記")
    lines.append("")
    lines.append(f"生成時間：{datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("")

    lines.append("## 📝 文件摘要")
    lines.append("")
    lines.append(analysis_result.summary)
    lines.append("")

    lines.append("## 🧠 重點整理")
    lines.append("")

    if analysis_result.key_points:
        for point in analysis_result.key_points:
            lines.append(f"- {point}")
    else:
        lines.append("- 本次未產生重點整理。")

    lines.append("")

    lines.append("## 🗺️ Mermaid 圖表")
    lines.append("")

    is_valid, _ = validate_mermaid(analysis_result.mermaid)

    if is_valid:
        lines.append(analysis_result.mermaid)
    else:
        lines.append("本次未產生可用的 Mermaid 圖表。")

    lines.append("")

    lines.append("## ❓ Quiz")
    lines.append("")

    if analysis_result.quiz:
        for index, item in enumerate(analysis_result.quiz, start=1):
            lines.append(f"### 第 {index} 題")
            lines.append("")
            lines.append(f"**Q：{item.question}**")
            lines.append("")
            lines.append(f"**A：{item.answer}**")
            lines.append("")
    else:
        lines.append("本次未產生 Quiz。")
        lines.append("")

    lines.append("## 🗂️ Flash Cards")
    lines.append("")

    if analysis_result.flashcards:
        for index, card in enumerate(analysis_result.flashcards, start=1):
            lines.append(f"### Flash Card {index}")
            lines.append("")
            lines.append(f"**正面：{card.front}**")
            lines.append("")
            lines.append(f"**背面：{card.back}**")
            lines.append("")
    else:
        lines.append("本次未產生 Flash Cards。")
        lines.append("")

    return "\n".join(lines)