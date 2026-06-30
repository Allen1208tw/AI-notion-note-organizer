import json
from datetime import datetime

from src.models.analysis_models import AnalysisResult


def build_json(
    document_name: str,
    analysis_result: AnalysisResult,
) -> str:
    """將分析結果轉換成 JSON 字串。"""

    data = {
        "document_name": document_name,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "summary": analysis_result.summary,
        "key_points": analysis_result.key_points,
        "mermaid": analysis_result.mermaid,
        "quiz": [
            {
                "question": item.question,
                "answer": item.answer,
            }
            for item in analysis_result.quiz
        ],
        "flashcards": [
            {
                "front": card.front,
                "back": card.back,
            }
            for card in analysis_result.flashcards
        ],
    }

    return json.dumps(
        data,
        ensure_ascii=False,
        indent=2,
    )