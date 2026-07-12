from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from src.database.database import get_database_session
from src.database.models import Chapter, Document, Flashcard, Quiz


def create_file_hash(file_bytes: bytes) -> str:
    """建立檔案 SHA-256 雜湊值。"""

    return hashlib.sha256(file_bytes).hexdigest()


def get_document_by_file_hash(
    file_hash: str,
) -> Optional[Document]:
    """依檔案雜湊值取得既有文件紀錄。"""

    with get_database_session() as session:
        statement = (
            select(Document)
            .where(Document.file_hash == file_hash)
            .options(selectinload(Document.chapters))
        )

        return session.scalar(statement)


def create_or_update_document(
    file_name: str,
    file_extension: str,
    file_size_bytes: int,
    file_hash: str,
    metadata: dict,
    chapters: list[dict],
) -> Document:
    """
    建立或更新文件與 Module 紀錄。

    相同檔案雜湊值會更新既有紀錄，
    不會重複建立 documents 資料。
    """

    page_count = int(metadata.get("page_count", 0) or 0)

    character_count = int(
        metadata.get("character_count", 0) or 0
    )

    with get_database_session() as session:
        statement = (
            select(Document)
            .where(Document.file_hash == file_hash)
            .options(selectinload(Document.chapters))
        )

        document = session.scalar(statement)

        if document is None:
            document = Document(
                file_name=file_name,
                file_extension=file_extension,
                file_size_bytes=file_size_bytes,
                file_hash=file_hash,
                character_count=character_count,
                page_count=page_count,
                chapter_count=len(chapters),
                status="analyzed",
            )

            session.add(document)
            session.flush()

        else:
            document.file_name = file_name
            document.file_extension = file_extension
            document.file_size_bytes = file_size_bytes
            document.character_count = character_count
            document.page_count = page_count
            document.chapter_count = len(chapters)
            document.status = "analyzed"
            document.updated_at = datetime.utcnow()

            for existing_chapter in document.chapters:
                session.delete(existing_chapter)

            session.flush()

        for chapter_order, chapter_data in enumerate(
            chapters,
            start=1,
        ):
            chapter = Chapter(
                document_id=document.id,
                source_chapter_id=str(
                    chapter_data.get(
                        "chapter_id",
                        chapter_order,
                    )
                ),
                chapter_order=chapter_order,
                title=str(
                    chapter_data.get(
                        "title",
                        f"第 {chapter_order} 章",
                    )
                ),
                character_count=len(
                    str(chapter_data.get("content", ""))
                ),
                export_status="pending",
                visual_cache_status="pending",
                note_cache_status="pending",
            )

            session.add(chapter)

        session.commit()
        session.refresh(document)

        return document


def list_documents() -> list[Document]:
    """取得所有歷史文件，最新的排最前面。"""

    with get_database_session() as session:
        statement = (
            select(Document)
            .options(selectinload(Document.chapters))
            .order_by(Document.updated_at.desc())
        )

        return list(session.scalars(statement).all())


def get_document_with_chapters(
    document_id: str,
) -> Optional[Document]:
    """取得單一文件與其 Module 紀錄。"""

    with get_database_session() as session:
        statement = (
            select(Document)
            .where(Document.id == document_id)
            .options(selectinload(Document.chapters))
        )

        return session.scalar(statement)


def mark_document_exporting(
    document_id: str,
) -> None:
    """將文件狀態更新為 Notion 匯出中。"""

    with get_database_session() as session:
        document = session.get(Document, document_id)

        if document is None:
            return

        document.status = "exporting"
        document.updated_at = datetime.utcnow()

        session.commit()


def _find_chapter_record(
    chapters: list[Chapter],
    chapter_data: dict,
) -> Optional[Chapter]:
    """
    依匯出結果中的 chapter_id 或 title，
    找到對應的 SQLite Chapter 紀錄。
    """

    source_chapter_id = str(
        chapter_data.get(
            "chapter_id",
            chapter_data.get("source_chapter_id", ""),
        )
    )

    chapter_title = str(
        chapter_data.get(
            "chapter_title",
            chapter_data.get("title", ""),
        )
    )

    for chapter in chapters:
        if (
            source_chapter_id
            and chapter.source_chapter_id == source_chapter_id
        ):
            return chapter

    for chapter in chapters:
        if chapter_title and chapter.title == chapter_title:
            return chapter

    return None


def update_document_export_result(
    document_id: str,
    export_result: dict,
) -> None:
    """
    將 Notion 匯出結果回寫到 SQLite。

    可處理成功、部分失敗與完整失敗的情況。
    """

    with get_database_session() as session:
        statement = (
            select(Document)
            .where(Document.id == document_id)
            .options(selectinload(Document.chapters))
        )

        document = session.scalar(statement)

        if document is None:
            return

        document.notion_parent_page_id = export_result.get(
            "parent_page_id"
        )

        document.notion_parent_url = export_result.get(
            "parent_page_url"
        )

        completed_chapters = export_result.get(
            "completed_chapters",
            [],
        )

        failed_chapters = export_result.get(
            "failed_chapters",
            [],
        )

        for completed_chapter in completed_chapters:
            if not isinstance(completed_chapter, dict):
                continue

            chapter_record = _find_chapter_record(
                document.chapters,
                completed_chapter,
            )

            if chapter_record is None:
                continue

            chapter_record.export_status = "completed"
            chapter_record.visual_cache_status = "completed"
            chapter_record.note_cache_status = "completed"

            notion_page_url = completed_chapter.get(
                "notion_page_url"
            )

            if not notion_page_url:
                notion_page_url = completed_chapter.get(
                    "page_url"
                )

            if notion_page_url:
                chapter_record.notion_page_url = notion_page_url

            chapter_record.updated_at = datetime.utcnow()

        for failed_chapter in failed_chapters:
            if not isinstance(failed_chapter, dict):
                continue

            chapter_record = _find_chapter_record(
                document.chapters,
                failed_chapter,
            )

            if chapter_record is None:
                continue

            chapter_record.export_status = "failed"
            chapter_record.updated_at = datetime.utcnow()

        is_finished = export_result.get(
            "is_finished",
            False,
        )

        if is_finished:
            document.status = "completed"

        elif failed_chapters:
            document.status = "failed"

        else:
            document.status = "exporting"

        document.updated_at = datetime.utcnow()

        session.commit()


def save_chapter_learning_items(
    document_id: str,
    source_chapter_id: str,
    chapter_note,
) -> dict:
    """
    將單一 Module 詳細學習筆記中的 Quiz / Flash Cards
    寫入 SQLite。

    每次重新生成同一章筆記時，
    會先刪除該章舊題目與舊卡片，再寫入最新版本。
    """

    with get_database_session() as session:
        statement = (
            select(Chapter)
            .where(Chapter.document_id == document_id)
            .where(Chapter.source_chapter_id == str(source_chapter_id))
        )

        chapter = session.scalar(statement)

        if chapter is None:
            return {
                "saved": False,
                "quiz_count": 0,
                "flashcard_count": 0,
                "reason": "找不到對應章節紀錄",
            }

        old_quizzes_statement = (
            select(Quiz)
            .where(Quiz.document_id == document_id)
            .where(Quiz.chapter_id == chapter.id)
        )

        old_quizzes = list(
            session.scalars(old_quizzes_statement).all()
        )

        for old_quiz in old_quizzes:
            session.delete(old_quiz)

        old_flashcards_statement = (
            select(Flashcard)
            .where(Flashcard.document_id == document_id)
            .where(Flashcard.chapter_id == chapter.id)
        )

        old_flashcards = list(
            session.scalars(old_flashcards_statement).all()
        )

        for old_flashcard in old_flashcards:
            session.delete(old_flashcard)

        quiz_count = 0
        flashcard_count = 0

        for quiz_item in getattr(chapter_note, "quiz", []):
            question = str(
                getattr(quiz_item, "question", "")
            ).strip()

            answer = str(
                getattr(quiz_item, "answer", "")
            ).strip()

            explanation = str(
                getattr(quiz_item, "explanation", "")
            ).strip()

            if not question or not answer:
                continue

            quiz = Quiz(
                document_id=document_id,
                chapter_id=chapter.id,
                question=question,
                correct_answer=answer,
                explanation=explanation,
                difficulty="medium",
            )

            session.add(quiz)
            quiz_count += 1

        for card_item in getattr(chapter_note, "flashcards", []):
            front = str(
                getattr(card_item, "front", "")
            ).strip()

            back = str(
                getattr(card_item, "back", "")
            ).strip()

            if not front or not back:
                continue

            flashcard = Flashcard(
                document_id=document_id,
                chapter_id=chapter.id,
                front=front,
                back=back,
            )

            session.add(flashcard)
            flashcard_count += 1

        chapter.note_cache_status = "completed"
        chapter.updated_at = datetime.utcnow()

        session.commit()

        return {
            "saved": True,
            "quiz_count": quiz_count,
            "flashcard_count": flashcard_count,
            "reason": "",
        }


def count_chapter_learning_items(
    document_id: str,
    source_chapter_id: str,
) -> dict:
    """取得單一章節已儲存的 Quiz / Flash Card 數量。"""

    with get_database_session() as session:
        chapter_statement = (
            select(Chapter)
            .where(Chapter.document_id == document_id)
            .where(Chapter.source_chapter_id == str(source_chapter_id))
        )

        chapter = session.scalar(chapter_statement)

        if chapter is None:
            return {
                "quiz_count": 0,
                "flashcard_count": 0,
            }

        quiz_count_statement = (
            select(func.count(Quiz.id))
            .where(Quiz.document_id == document_id)
            .where(Quiz.chapter_id == chapter.id)
        )

        flashcard_count_statement = (
            select(func.count(Flashcard.id))
            .where(Flashcard.document_id == document_id)
            .where(Flashcard.chapter_id == chapter.id)
        )

        quiz_count = session.scalar(quiz_count_statement) or 0
        flashcard_count = session.scalar(flashcard_count_statement) or 0

        return {
            "quiz_count": int(quiz_count),
            "flashcard_count": int(flashcard_count),
        }


def count_document_learning_items(
    document_id: str,
) -> dict:
    """取得整份文件已儲存的 Quiz / Flash Card 數量。"""

    with get_database_session() as session:
        quiz_count_statement = (
            select(func.count(Quiz.id))
            .where(Quiz.document_id == document_id)
        )

        flashcard_count_statement = (
            select(func.count(Flashcard.id))
            .where(Flashcard.document_id == document_id)
        )

        quiz_count = session.scalar(quiz_count_statement) or 0
        flashcard_count = session.scalar(flashcard_count_statement) or 0

        return {
            "quiz_count": int(quiz_count),
            "flashcard_count": int(flashcard_count),
        }