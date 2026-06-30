from pydantic import BaseModel, Field


class QuizItem(BaseModel):
    question: str
    answer: str


class FlashCardItem(BaseModel):
    front: str
    back: str


class ChunkAnalysisResult(BaseModel):
    chunk_summary: str
    key_points: list[str] = Field(default_factory=list)
    terms: list[str] = Field(default_factory=list)
    quiz_candidates: list[QuizItem] = Field(default_factory=list)
    flashcard_candidates: list[FlashCardItem] = Field(default_factory=list)


class AnalysisResult(BaseModel):
    summary: str
    key_points: list[str] = Field(default_factory=list)
    mermaid: str = ""
    quiz: list[QuizItem] = Field(default_factory=list)
    flashcards: list[FlashCardItem] = Field(default_factory=list)