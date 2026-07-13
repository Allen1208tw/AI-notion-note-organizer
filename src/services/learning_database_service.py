from __future__ import annotations

import hashlib
import json
import re
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from src.config.settings import OUTPUT_DIR
from src.database.database import get_database_session
from src.database.models import (
    Chapter,
    Document,
    Flashcard,
    FlashcardReview,
    Quiz,
    QuizAttempt,
    ReviewSchedule,
    WeakPoint,
)


def _get_model_column_names(model_class) -> set[str]:
    """取得 SQLAlchemy Model 實際存在的欄位名稱。"""

    return set(model_class.__table__.columns.keys())


def _filter_model_kwargs(model_class, data: dict) -> dict:
    """
    只保留 Model 實際存在的欄位。

    避免 SQLAlchemy 出現：
    'xxx' is an invalid keyword argument for Model
    """

    column_names = _get_model_column_names(model_class)

    return {
        key: value
        for key, value in data.items()
        if key in column_names
    }


def _safe_setattr(model_instance, attr_name: str, value) -> None:
    """安全設定 Model 屬性。"""

    if hasattr(model_instance, attr_name):
        setattr(model_instance, attr_name, value)


def _new_id() -> str:
    """產生 UUID 字串 ID。"""

    return str(uuid.uuid4())


def _model_uses_string_id(model_class) -> bool:
    """
    判斷 Model 的 ID 是否使用字串。

    Integer ID 通常交給資料庫自動產生。
    String ID 則自動補入 UUID。
    """

    try:
        column = model_class.__table__.columns.get("id")

        if column is None:
            return False

        column_type = str(column.type).lower()

        return (
            "char" in column_type
            or "string" in column_type
            or "varchar" in column_type
            or "text" in column_type
        )
    except Exception:
        return False


def _maybe_add_id(model_class, data: dict) -> dict:
    """如果 Model 使用字串 ID，且資料沒有 ID，自動補入 UUID。"""

    result = dict(data)

    if "id" not in _get_model_column_names(model_class):
        return result

    if result.get("id"):
        return result

    if _model_uses_string_id(model_class):
        result["id"] = _new_id()

    return result


def _safe_int(value, default: int = 0) -> int:
    """安全轉換成整數。"""

    try:
        if value is None:
            return default

        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_text(value, default: str = "") -> str:
    """安全轉換成字串。"""

    if value is None:
        return default

    try:
        return str(value)
    except Exception:
        return default


def create_file_hash(file_bytes: bytes) -> str:
    """依照檔案 bytes 建立 SHA256 Hash。"""

    return hashlib.sha256(file_bytes).hexdigest()


def _safe_file_name(file_name: str) -> str:
    """將文件名稱轉成可用於資料夾或檔名的安全名稱。"""

    safe_name = Path(file_name).stem
    safe_name = re.sub(r'[\\/:*?"<>|]+', "_", safe_name)
    safe_name = safe_name.strip()

    if not safe_name:
        safe_name = "untitled_document"

    return safe_name


def _get_export_job_file_candidates(file_name: str) -> list[Path]:
    """取得可能的 Export Job State 檔案路徑。"""

    safe_name = _safe_file_name(file_name)
    export_jobs_dir = OUTPUT_DIR / "export_jobs"

    candidates = [
        export_jobs_dir / f"{safe_name}_detailed_notion_export_state.json",
        export_jobs_dir / f"{safe_name}.json",
    ]

    if export_jobs_dir.exists():
        candidates.extend(export_jobs_dir.glob(f"{safe_name}*.json"))

    unique_candidates: list[Path] = []

    for path in candidates:
        if path not in unique_candidates:
            unique_candidates.append(path)

    return unique_candidates


def _get_chapter_cache_dir(file_name: str) -> Path:
    """取得章節快取資料夾。"""

    return OUTPUT_DIR / "chapter_cache" / _safe_file_name(file_name)


def _get_path_size(path: Path) -> int:
    """計算檔案或資料夾大小。"""

    if not path.exists():
        return 0

    if path.is_file():
        try:
            return path.stat().st_size
        except OSError:
            return 0

    total_size = 0

    try:
        for item in path.rglob("*"):
            if item.is_file():
                try:
                    total_size += item.stat().st_size
                except OSError:
                    continue
    except OSError:
        return total_size

    return total_size


def _format_bytes(size_bytes: int) -> str:
    """將 Bytes 轉成容易閱讀的格式。"""

    size_bytes = max(_safe_int(size_bytes), 0)

    if size_bytes < 1024:
        return f"{size_bytes} B"

    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.2f} KB"

    if size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.2f} MB"

    return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


def _delete_review_schedules_for_items(
    session,
    item_type: str,
    item_ids: list[str],
) -> None:
    """刪除指定類型與 ID 的複習排程。"""

    if not item_ids:
        return

    session.query(ReviewSchedule).filter(
        ReviewSchedule.item_type == item_type,
        ReviewSchedule.item_id.in_(item_ids),
    ).delete(synchronize_session=False)


def _delete_document_learning_records(
    session,
    document_id: int | str,
    delete_chapters: bool = True,
) -> None:
    """
    刪除指定文件的學習資料。

    用於重新分析文件時，避免殘留舊 Quiz、Flashcard、
    QuizAttempt、WeakPoint、ReviewSchedule 等孤兒資料。
    """

    quiz_ids = [
        row[0]
        for row in session.query(Quiz.id)
        .filter(Quiz.document_id == document_id)
        .all()
    ]

    flashcard_ids = [
        row[0]
        for row in session.query(Flashcard.id)
        .filter(Flashcard.document_id == document_id)
        .all()
    ]

    if quiz_ids:
        session.query(WeakPoint).filter(
            WeakPoint.quiz_id.in_(quiz_ids)
        ).delete(synchronize_session=False)

        session.query(QuizAttempt).filter(
            QuizAttempt.quiz_id.in_(quiz_ids)
        ).delete(synchronize_session=False)

        _delete_review_schedules_for_items(
            session=session,
            item_type="quiz",
            item_ids=quiz_ids,
        )

    if flashcard_ids:
        session.query(FlashcardReview).filter(
            FlashcardReview.flashcard_id.in_(flashcard_ids)
        ).delete(synchronize_session=False)

        _delete_review_schedules_for_items(
            session=session,
            item_type="flashcard",
            item_ids=flashcard_ids,
        )

    session.query(WeakPoint).filter(
        WeakPoint.document_id == document_id
    ).delete(synchronize_session=False)

    session.query(ReviewSchedule).filter(
        ReviewSchedule.document_id == document_id
    ).delete(synchronize_session=False)

    session.query(Quiz).filter(
        Quiz.document_id == document_id
    ).delete(synchronize_session=False)

    session.query(Flashcard).filter(
        Flashcard.document_id == document_id
    ).delete(synchronize_session=False)

    if delete_chapters:
        session.query(Chapter).filter(
            Chapter.document_id == document_id
        ).delete(synchronize_session=False)

    session.flush()


def get_document_by_file_hash(file_hash: str) -> Optional[Document]:
    """依照檔案 Hash 取得文件。"""

    with get_database_session() as session:
        statement = select(Document).where(
            Document.file_hash == file_hash
        )

        document = session.execute(statement).scalars().first()

        if document is not None:
            session.expunge(document)

        return document


def create_or_update_document(
    file_name: str,
    file_extension: str,
    file_size_bytes: int,
    file_hash: str,
    metadata: dict,
    chapters: list[dict],
) -> Document:
    """建立或更新文件與章節資料。"""

    metadata = metadata or {}
    chapters = chapters or []

    with get_database_session() as session:
        statement = select(Document).where(
            Document.file_hash == file_hash
        )

        document = session.execute(statement).scalars().first()
        now = datetime.utcnow()

        document_data = {
            "file_name": file_name,
            "file_extension": file_extension,
            "file_size_bytes": _safe_int(file_size_bytes),
            "file_hash": file_hash,
            "page_count": _safe_int(metadata.get("page_count")),
            "character_count": _safe_int(
                metadata.get("character_count")
            ),
            "paragraph_count": _safe_int(
                metadata.get("paragraph_count")
            ),
            "chapter_count": len(chapters),
            "status": "analyzed",
            "export_status": "pending",
            "updated_at": now,
        }

        if document is None:
            document_data["created_at"] = now
            document_data = _maybe_add_id(
                Document,
                document_data,
            )

            document = Document(
                **_filter_model_kwargs(
                    Document,
                    document_data,
                )
            )

            session.add(document)
            session.flush()

        else:
            for key, value in document_data.items():
                _safe_setattr(
                    document,
                    key,
                    value,
                )

            _safe_setattr(
                document,
                "notion_parent_page_id",
                None,
            )

            _safe_setattr(
                document,
                "notion_parent_url",
                None,
            )

            _delete_document_learning_records(
                session=session,
                document_id=document.id,
                delete_chapters=True,
            )

        for index, chapter in enumerate(chapters, start=1):
            chapter = chapter or {}

            source_chapter_id = _safe_text(
                chapter.get("chapter_id"),
                str(index),
            )

            if not source_chapter_id.strip():
                source_chapter_id = str(index)

            chapter_content = _safe_text(
                chapter.get("content"),
            )

            subsections = chapter.get("subsections") or []

            chapter_data = {
                "document_id": document.id,
                "source_chapter_id": source_chapter_id,
                "chapter_order": index,
                "title": _safe_text(
                    chapter.get("title"),
                    f"Module {index}",
                ),
                "source": chapter.get("source"),
                "start_index": chapter.get("start_index"),
                "end_index": chapter.get("end_index"),
                "character_count": len(chapter_content),
                "subsection_count": len(subsections),
                "export_status": "pending",
                "visual_cache_status": "pending",
                "note_cache_status": "pending",
                "notion_page_id": None,
                "notion_page_url": None,
                "created_at": now,
                "updated_at": now,
            }

            chapter_data = _maybe_add_id(
                Chapter,
                chapter_data,
            )

            chapter_record = Chapter(
                **_filter_model_kwargs(
                    Chapter,
                    chapter_data,
                )
            )

            session.add(chapter_record)

        session.commit()
        session.refresh(document)
        session.expunge(document)

        return document


def list_documents() -> list[Document]:
    """列出所有文件。"""

    with get_database_session() as session:
        statement = (
            select(Document)
            .options(selectinload(Document.chapters))
            .order_by(Document.updated_at.desc())
        )

        documents = list(
            session.execute(statement).scalars().unique().all()
        )

        for document in documents:
            document.chapters.sort(
                key=lambda chapter: getattr(
                    chapter,
                    "chapter_order",
                    0,
                )
            )
            session.expunge(document)

        return documents


def get_document_with_chapters(
    document_id: int | str,
) -> Optional[Document]:
    """取得文件與章節。"""

    with get_database_session() as session:
        statement = (
            select(Document)
            .where(Document.id == document_id)
            .options(selectinload(Document.chapters))
        )

        document = session.execute(
            statement
        ).scalars().unique().first()

        if document is not None:
            document.chapters.sort(
                key=lambda chapter: getattr(
                    chapter,
                    "chapter_order",
                    0,
                )
            )
            session.expunge(document)

        return document


def mark_document_exporting(
    document_id: int | str,
) -> None:
    """標記文件正在匯出。"""

    with get_database_session() as session:
        document = session.get(
            Document,
            document_id,
        )

        if document is None:
            return

        document.export_status = "exporting"
        document.updated_at = datetime.utcnow()

        session.commit()


def _find_chapter_record(
    session,
    document_id: int | str,
    source_chapter_id: str,
) -> Optional[Chapter]:
    """
    尋找指定文件下的章節。

    優先使用 source_chapter_id。
    找不到時再嘗試 chapter_order。
    """

    source_chapter_id = _safe_text(
        source_chapter_id
    ).strip()

    if source_chapter_id:
        statement = select(Chapter).where(
            Chapter.document_id == document_id,
            Chapter.source_chapter_id == source_chapter_id,
        )

        chapter = session.execute(
            statement
        ).scalars().first()

        if chapter is not None:
            return chapter

    try:
        chapter_order = int(source_chapter_id)
    except (TypeError, ValueError):
        chapter_order = None

    if chapter_order is not None:
        statement = select(Chapter).where(
            Chapter.document_id == document_id,
            Chapter.chapter_order == chapter_order,
        )

        chapter = session.execute(
            statement
        ).scalars().first()

        if chapter is not None:
            return chapter

    statement = (
        select(Chapter)
        .where(Chapter.document_id == document_id)
        .order_by(Chapter.chapter_order.asc())
    )

    return session.execute(
        statement
    ).scalars().first()


def update_document_export_result(
    document_id: int | str,
    export_result: dict,
) -> None:
    """
    依照 Notion 匯出結果更新文件與章節狀態。

    相容 completed_chapters / failed_chapters 內的項目格式：

    1. 字典
       {
           "chapter_id": "1",
           "notion_page_id": "...",
           "notion_page_url": "...",
       }

    2. 字串
       "1"

    3. 整數
       1
    """

    def normalize_chapter_item(item) -> dict:
        """將不同格式的章節結果統一轉成字典。"""

        if isinstance(item, dict):
            return item

        if isinstance(item, (str, int)):
            return {
                "chapter_id": str(item),
            }

        chapter_id = getattr(
            item,
            "chapter_id",
            None,
        )

        source_chapter_id = getattr(
            item,
            "source_chapter_id",
            None,
        )

        chapter_order = getattr(
            item,
            "chapter_order",
            None,
        )

        notion_page_id = getattr(
            item,
            "notion_page_id",
            None,
        )

        notion_page_url = getattr(
            item,
            "notion_page_url",
            None,
        )

        chapter_title = getattr(
            item,
            "chapter_title",
            None,
        )

        error = getattr(
            item,
            "error",
            None,
        )

        return {
            "chapter_id": (
                chapter_id
                or source_chapter_id
                or chapter_order
                or ""
            ),
            "notion_page_id": notion_page_id,
            "notion_page_url": notion_page_url,
            "chapter_title": chapter_title,
            "error": error,
        }

    if not isinstance(export_result, dict):
        return

    with get_database_session() as session:
        document = session.get(
            Document,
            document_id,
        )

        if document is None:
            return

        raw_completed_chapters = (
            export_result.get("completed_chapters")
            or []
        )

        raw_failed_chapters = (
            export_result.get("failed_chapters")
            or []
        )

        if not isinstance(
            raw_completed_chapters,
            (list, tuple, set),
        ):
            raw_completed_chapters = [
                raw_completed_chapters
            ]

        if not isinstance(
            raw_failed_chapters,
            (list, tuple, set),
        ):
            raw_failed_chapters = [
                raw_failed_chapters
            ]

        completed_chapters = [
            normalize_chapter_item(item)
            for item in raw_completed_chapters
        ]

        failed_chapters = [
            normalize_chapter_item(item)
            for item in raw_failed_chapters
        ]

        parent_page_id = (
            export_result.get("parent_page_id")
            or export_result.get(
                "notion_parent_page_id"
            )
        )

        parent_page_url = (
            export_result.get("parent_page_url")
            or export_result.get(
                "notion_parent_url"
            )
        )

        if parent_page_id:
            _safe_setattr(
                document,
                "notion_parent_page_id",
                str(parent_page_id),
            )

        if parent_page_url:
            _safe_setattr(
                document,
                "notion_parent_url",
                str(parent_page_url),
            )

        completed_ids: set[str] = set()
        failed_ids: set[str] = set()

        for item in completed_chapters:
            chapter_identifier = str(
                item.get("chapter_id")
                or item.get("source_chapter_id")
                or item.get("chapter_order")
                or ""
            ).strip()

            if not chapter_identifier:
                continue

            completed_ids.add(
                chapter_identifier
            )

            chapter = _find_chapter_record(
                session=session,
                document_id=document_id,
                source_chapter_id=chapter_identifier,
            )

            if chapter is None:
                continue

            _safe_setattr(
                chapter,
                "export_status",
                "completed",
            )

            notion_page_id = item.get(
                "notion_page_id"
            )

            notion_page_url = item.get(
                "notion_page_url"
            )

            if notion_page_id:
                _safe_setattr(
                    chapter,
                    "notion_page_id",
                    str(notion_page_id),
                )

            if notion_page_url:
                _safe_setattr(
                    chapter,
                    "notion_page_url",
                    str(notion_page_url),
                )

            _safe_setattr(
                chapter,
                "updated_at",
                datetime.utcnow(),
            )

        for item in failed_chapters:
            chapter_identifier = str(
                item.get("chapter_id")
                or item.get("source_chapter_id")
                or item.get("chapter_order")
                or ""
            ).strip()

            if not chapter_identifier:
                continue

            failed_ids.add(
                chapter_identifier
            )

            chapter = _find_chapter_record(
                session=session,
                document_id=document_id,
                source_chapter_id=chapter_identifier,
            )

            if chapter is None:
                continue

            _safe_setattr(
                chapter,
                "export_status",
                "failed",
            )

            _safe_setattr(
                chapter,
                "updated_at",
                datetime.utcnow(),
            )

        all_chapters = (
            session.query(Chapter)
            .filter(
                Chapter.document_id == document_id
            )
            .order_by(
                Chapter.chapter_order.asc()
            )
            .all()
        )

        if all_chapters and all(
            getattr(
                chapter,
                "export_status",
                "pending",
            )
            == "completed"
            for chapter in all_chapters
        ):
            _safe_setattr(
                document,
                "export_status",
                "completed",
            )

        elif failed_ids:
            _safe_setattr(
                document,
                "export_status",
                "failed",
            )

        elif completed_ids:
            _safe_setattr(
                document,
                "export_status",
                "partial",
            )

        else:
            _safe_setattr(
                document,
                "export_status",
                "pending",
            )

        _safe_setattr(
            document,
            "updated_at",
            datetime.utcnow(),
        )

        session.commit()


def _extract_quiz_items(chapter_note) -> list:
    """安全取得章節筆記中的 Quiz。"""

    quiz_items = getattr(
        chapter_note,
        "quiz",
        None,
    )

    if quiz_items is None:
        quiz_items = getattr(
            chapter_note,
            "quizzes",
            None,
        )

    return list(quiz_items or [])


def _extract_flashcard_items(chapter_note) -> list:
    """安全取得章節筆記中的 Flashcards。"""

    flashcard_items = getattr(
        chapter_note,
        "flashcards",
        None,
    )

    if flashcard_items is None:
        flashcard_items = getattr(
            chapter_note,
            "flash_cards",
            None,
        )

    return list(flashcard_items or [])


def save_chapter_learning_items(
    document_id: int | str,
    source_chapter_id: str,
    chapter_note,
) -> dict:
    """將章節詳細筆記中的 Quiz 與 Flashcards 寫入 SQLite。"""

    with get_database_session() as session:
        chapter = _find_chapter_record(
            session=session,
            document_id=document_id,
            source_chapter_id=str(source_chapter_id),
        )

        if chapter is None:
            return {
                "saved": False,
                "reason": "找不到對應章節",
                "quiz_count": 0,
                "flashcard_count": 0,
            }

        old_quizzes = (
            session.query(Quiz)
            .filter(
                Quiz.document_id == document_id,
                Quiz.chapter_id == chapter.id,
            )
            .all()
        )

        old_quiz_ids = [
            quiz.id
            for quiz in old_quizzes
        ]

        if old_quiz_ids:
            session.query(WeakPoint).filter(
                WeakPoint.quiz_id.in_(old_quiz_ids)
            ).delete(synchronize_session=False)

            session.query(QuizAttempt).filter(
                QuizAttempt.quiz_id.in_(old_quiz_ids)
            ).delete(synchronize_session=False)

            _delete_review_schedules_for_items(
                session=session,
                item_type="quiz",
                item_ids=old_quiz_ids,
            )

        session.query(Quiz).filter(
            Quiz.document_id == document_id,
            Quiz.chapter_id == chapter.id,
        ).delete(synchronize_session=False)

        old_flashcards = (
            session.query(Flashcard)
            .filter(
                Flashcard.document_id == document_id,
                Flashcard.chapter_id == chapter.id,
            )
            .all()
        )

        old_flashcard_ids = [
            flashcard.id
            for flashcard in old_flashcards
        ]

        if old_flashcard_ids:
            session.query(FlashcardReview).filter(
                FlashcardReview.flashcard_id.in_(
                    old_flashcard_ids
                )
            ).delete(synchronize_session=False)

            _delete_review_schedules_for_items(
                session=session,
                item_type="flashcard",
                item_ids=old_flashcard_ids,
            )

        session.query(Flashcard).filter(
            Flashcard.document_id == document_id,
            Flashcard.chapter_id == chapter.id,
        ).delete(synchronize_session=False)

        session.flush()

        quiz_count = 0
        flashcard_count = 0
        now = datetime.utcnow()

        for quiz_item in _extract_quiz_items(
            chapter_note
        ):
            question = _safe_text(
                getattr(
                    quiz_item,
                    "question",
                    "",
                )
            ).strip()

            correct_answer = _safe_text(
                getattr(
                    quiz_item,
                    "answer",
                    getattr(
                        quiz_item,
                        "correct_answer",
                        "",
                    ),
                )
            ).strip()

            explanation = _safe_text(
                getattr(
                    quiz_item,
                    "explanation",
                    "",
                )
            ).strip()

            difficulty = _safe_text(
                getattr(
                    quiz_item,
                    "difficulty",
                    "medium",
                ),
                "medium",
            ).strip()

            if not question or not correct_answer:
                continue

            quiz_data = {
                "document_id": str(document_id),
                "chapter_id": chapter.id,
                "question": question,
                "correct_answer": correct_answer,
                "explanation": explanation or None,
                "difficulty": difficulty or "medium",
                "created_at": now,
                "updated_at": now,
            }

            quiz_data = _maybe_add_id(
                Quiz,
                quiz_data,
            )

            quiz = Quiz(
                **_filter_model_kwargs(
                    Quiz,
                    quiz_data,
                )
            )

            session.add(quiz)
            quiz_count += 1

        for flashcard_item in _extract_flashcard_items(
            chapter_note
        ):
            front = _safe_text(
                getattr(
                    flashcard_item,
                    "front",
                    "",
                )
            ).strip()

            back = _safe_text(
                getattr(
                    flashcard_item,
                    "back",
                    "",
                )
            ).strip()

            if not front or not back:
                continue

            flashcard_data = {
                "document_id": str(document_id),
                "chapter_id": chapter.id,
                "front": front,
                "back": back,
                "created_at": now,
                "updated_at": now,
            }

            flashcard_data = _maybe_add_id(
                Flashcard,
                flashcard_data,
            )

            flashcard = Flashcard(
                **_filter_model_kwargs(
                    Flashcard,
                    flashcard_data,
                )
            )

            session.add(flashcard)
            flashcard_count += 1

        chapter.note_cache_status = "completed"
        chapter.updated_at = now

        session.commit()

        return {
            "saved": True,
            "reason": "",
            "quiz_count": quiz_count,
            "flashcard_count": flashcard_count,
        }


def count_chapter_learning_items(
    document_id: int | str,
    source_chapter_id: str,
) -> dict:
    """統計單一章節的 Quiz 與 Flashcards 數量。"""

    with get_database_session() as session:
        chapter = _find_chapter_record(
            session=session,
            document_id=document_id,
            source_chapter_id=str(source_chapter_id),
        )

        if chapter is None:
            return {
                "quiz_count": 0,
                "flashcard_count": 0,
            }

        quiz_count = (
            session.query(func.count(Quiz.id))
            .filter(
                Quiz.document_id == document_id,
                Quiz.chapter_id == chapter.id,
            )
            .scalar()
        )

        flashcard_count = (
            session.query(func.count(Flashcard.id))
            .filter(
                Flashcard.document_id == document_id,
                Flashcard.chapter_id == chapter.id,
            )
            .scalar()
        )

        return {
            "quiz_count": quiz_count or 0,
            "flashcard_count": flashcard_count or 0,
        }


def count_document_learning_items(
    document_id: int | str,
) -> dict:
    """統計整份文件的 Quiz、Flashcards 與弱點數量。"""

    with get_database_session() as session:
        quiz_count = (
            session.query(func.count(Quiz.id))
            .filter(Quiz.document_id == document_id)
            .scalar()
        )

        flashcard_count = (
            session.query(func.count(Flashcard.id))
            .filter(Flashcard.document_id == document_id)
            .scalar()
        )

        weak_point_count = (
            session.query(func.count(WeakPoint.id))
            .filter(
                WeakPoint.document_id == document_id,
                WeakPoint.status != "mastered",
            )
            .scalar()
        )

        return {
            "quiz_count": quiz_count or 0,
            "flashcard_count": flashcard_count or 0,
            "weak_point_count": weak_point_count or 0,
        }


def get_document_storage_usage(
    document_id: int | str,
) -> dict:
    """估算文件相關本機資料佔用空間。"""

    with get_database_session() as session:
        document = session.get(
            Document,
            document_id,
        )

        if document is None:
            return {
                "found": False,
                "database_size_bytes": 0,
                "cache_size_bytes": 0,
                "export_state_size_bytes": 0,
                "total_size_bytes": 0,
                "total_size_text": "0 B",
            }

        file_name = document.file_name

        quiz_count = (
            session.query(func.count(Quiz.id))
            .filter(Quiz.document_id == document_id)
            .scalar()
            or 0
        )

        flashcard_count = (
            session.query(func.count(Flashcard.id))
            .filter(Flashcard.document_id == document_id)
            .scalar()
            or 0
        )

        chapter_count = (
            session.query(func.count(Chapter.id))
            .filter(Chapter.document_id == document_id)
            .scalar()
            or 0
        )

        attempt_count = (
            session.query(func.count(QuizAttempt.id))
            .join(
                Quiz,
                QuizAttempt.quiz_id == Quiz.id,
            )
            .filter(Quiz.document_id == document_id)
            .scalar()
            or 0
        )

        weak_point_count = (
            session.query(func.count(WeakPoint.id))
            .filter(WeakPoint.document_id == document_id)
            .scalar()
            or 0
        )

        cache_dir = _get_chapter_cache_dir(
            file_name
        )

        cache_size = _get_path_size(
            cache_dir
        )

        export_state_size = 0

        for path in _get_export_job_file_candidates(
            file_name
        ):
            export_state_size += _get_path_size(
                path
            )

        approximate_database_size = (
            _safe_int(document.file_size_bytes)
            + _safe_int(document.character_count)
            + chapter_count * 1024
            + quiz_count * 2048
            + flashcard_count * 1024
            + attempt_count * 1024
            + weak_point_count * 2048
        )

        total_size = (
            approximate_database_size
            + cache_size
            + export_state_size
        )

        return {
            "found": True,
            "file_name": file_name,
            "chapter_count": chapter_count,
            "quiz_count": quiz_count,
            "flashcard_count": flashcard_count,
            "attempt_count": attempt_count,
            "weak_point_count": weak_point_count,
            "database_size_bytes": approximate_database_size,
            "cache_size_bytes": cache_size,
            "export_state_size_bytes": export_state_size,
            "total_size_bytes": total_size,
            "database_size_text": _format_bytes(
                approximate_database_size
            ),
            "cache_size_text": _format_bytes(
                cache_size
            ),
            "export_state_size_text": _format_bytes(
                export_state_size
            ),
            "total_size_text": _format_bytes(
                total_size
            ),
            "cache_dir": str(cache_dir),
        }


def delete_document_and_related_files(
    document_id: int | str,
    delete_cache: bool = True,
    delete_export_state: bool = True,
) -> dict:
    """
    刪除文件與本機相關資料。

    不會刪除 Notion 上已經建立的頁面。
    """

    deleted_files: list[str] = []
    deleted_dirs: list[str] = []

    with get_database_session() as session:
        document = session.get(
            Document,
            document_id,
        )

        if document is None:
            return {
                "deleted": False,
                "reason": "找不到文件",
                "deleted_files": [],
                "deleted_dirs": [],
            }

        file_name = document.file_name

        _delete_document_learning_records(
            session=session,
            document_id=document_id,
            delete_chapters=True,
        )

        session.delete(document)
        session.commit()

    if delete_cache:
        cache_dir = _get_chapter_cache_dir(
            file_name
        )

        if cache_dir.exists():
            try:
                shutil.rmtree(cache_dir)
                deleted_dirs.append(
                    str(cache_dir)
                )
            except OSError:
                pass

    if delete_export_state:
        for path in _get_export_job_file_candidates(
            file_name
        ):
            if path.exists() and path.is_file():
                try:
                    path.unlink()
                    deleted_files.append(
                        str(path)
                    )
                except OSError:
                    continue

    return {
        "deleted": True,
        "reason": "",
        "file_name": file_name,
        "deleted_files": deleted_files,
        "deleted_dirs": deleted_dirs,
    }


def export_documents_debug_json() -> str:
    """輸出目前文件資料，方便除錯。"""

    documents = list_documents()
    data: list[dict] = []

    for document in documents:
        data.append(
            {
                "id": getattr(
                    document,
                    "id",
                    "",
                ),
                "file_name": getattr(
                    document,
                    "file_name",
                    "",
                ),
                "file_extension": getattr(
                    document,
                    "file_extension",
                    "",
                ),
                "file_size_bytes": getattr(
                    document,
                    "file_size_bytes",
                    0,
                ),
                "status": getattr(
                    document,
                    "status",
                    "pending",
                ),
                "export_status": getattr(
                    document,
                    "export_status",
                    "pending",
                ),
                "chapter_count": len(
                    getattr(
                        document,
                        "chapters",
                        [],
                    )
                    or []
                ),
                "created_at": str(
                    getattr(
                        document,
                        "created_at",
                        "",
                    )
                ),
                "updated_at": str(
                    getattr(
                        document,
                        "updated_at",
                        "",
                    )
                ),
            }
        )

    return json.dumps(
        data,
        ensure_ascii=False,
        indent=2,
    )