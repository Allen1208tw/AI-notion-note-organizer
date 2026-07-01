from pydantic import BaseModel, Field


class CodeExample(BaseModel):
    """章節中的程式碼或語法範例。"""

    title: str
    language: str = "html"
    code: str
    explanation: str


class CommonMistake(BaseModel):
    """學習時容易混淆或做錯的地方。"""

    mistake: str
    correction: str


class ChapterQuizItem(BaseModel):
    """章節測驗題目。"""

    question: str
    answer: str
    explanation: str = ""


class ChapterFlashcardItem(BaseModel):
    """章節記憶卡。"""

    front: str
    back: str


class SubsectionNote(BaseModel):
    """子章節整理結果，例如 17-1、17-2。"""

    title: str
    summary: str
    key_points: list[str] = Field(default_factory=list)
    important_terms: list[str] = Field(default_factory=list)


class CalloutNote(BaseModel):
    """
    可轉成 Notion Callout 的重點標註。

    icon 可使用 Notion 支援的 Emoji，例如：
    💡 ⚠️ 📌 🧠 ✅ 🔥
    """

    title: str
    content: str
    icon: str = "💡"
    tone: str = "info"


class ComparisonTable(BaseModel):
    """
    比較表格。

    headers:
        表格欄位名稱

    rows:
        每一列資料，欄位順序需對應 headers
    """

    title: str
    headers: list[str] = Field(default_factory=list)
    rows: list[list[str]] = Field(default_factory=list)
    note: str = ""


class ImageInsight(BaseModel):
    """
    PDF 圖片、截圖、流程圖或 UI 示意圖的解讀結果。

    page_number:
        圖片所在 PDF 頁碼

    image_type:
        例如：
        - code_screenshot
        - ui_screenshot
        - diagram
        - table
        - workflow
        - illustration
    """

    page_number: int
    image_type: str
    title: str
    description: str
    learning_points: list[str] = Field(default_factory=list)
    related_subsection: str = ""


class PracticeTip(BaseModel):
    """可執行的練習建議。"""

    title: str
    instruction: str
    expected_result: str = ""


class ChapterLearningNote(BaseModel):
    """
    V1.5 的主章節詳細學習筆記。

    一個 ChapterLearningNote 對應一個 Module。
    """

    chapter_title: str

    learning_objectives: list[str] = Field(default_factory=list)

    chapter_summary: str

    plain_explanation: str

    key_points: list[str] = Field(default_factory=list)

    important_terms: list[str] = Field(default_factory=list)

    syntax_rules: list[str] = Field(default_factory=list)

    code_examples: list[CodeExample] = Field(default_factory=list)

    common_mistakes: list[CommonMistake] = Field(default_factory=list)

    subsections: list[SubsectionNote] = Field(default_factory=list)

    callout_notes: list[CalloutNote] = Field(default_factory=list)

    comparison_tables: list[ComparisonTable] = Field(default_factory=list)

    image_insights: list[ImageInsight] = Field(default_factory=list)

    practice_tips: list[PracticeTip] = Field(default_factory=list)

    mermaid: str = ""

    quiz: list[ChapterQuizItem] = Field(default_factory=list)

    flashcards: list[ChapterFlashcardItem] = Field(default_factory=list)