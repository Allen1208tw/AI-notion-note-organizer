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
)


def _get_model_column_names(model_class) -> set[str]:
    """取得 SQLAlchemy model 實際存在的欄位名稱。"""

    return set(model_class.__table__.columns.keys())


def _filter_model_kwargs(model_class, data: dict) -> dict:
    """
    只保留 model 實際存在的欄位。

    避免 SQLAlchemy 報：
    'xxx' is an invalid keyword argument for Model
    """

    column_names = _get_model_column_names(model_class)

    return {
        key: value
        for key, value in data.items()
        if key in column_names
    }


def _safe_setattr(model_instance, attr_name: str, value) -> None:
    """安全設定 model 屬性。"""

    if hasattr(model_instance, attr_name):
        setattr(model_instance, attr_name, value)


def _new_id() -> str:
    """產生 UUID 字串 ID。"""

    return str(uuid.uuid4())


def _model_uses_string_id(model_class) -> bool:
    """
    粗略判斷 model 的 id 是否偏向字串 UUID。

    若 id 欄位是 Integer autoincrement，通常不需要手動給 id。
    若 id 欄位是 String，通常需要手動給 UUID。
    """

    try:
        column = model_class.__table__.columns.get("id")
        column_type = str(column.type).lower()

        return "char" in column_type or "string" in column_type or "varchar" in column_type
    except Exception:
        return False


def _maybe_add_id(model_class, data: dict) -> dict:
    """如果 model 使用字串 ID，且 data 沒有 id，就自動補 UUID。"""

    if "id" not in _get_model_column_names(model_class):
        return data

    if data.get("id"):
        return data

    if _model_uses_string_id(model_class):
        data["id"] = _new_id()

    return data


def create_file_hash(file_bytes: bytes) -> str:
    """依照檔案 bytes 建立 SHA256 hash。"""

    return hashlib.sha256(file_bytes).hexdigest()


def _safe_file_name(file_name: str) -> str:
    """將文件名稱轉成可用於資料夾 / 檔名的安全名稱。"""

    safe_name = Path(file_name).stem
    safe_name = re.sub(r'[\\/:*?"<>|]+', "_", safe_name)
    safe_name = safe_name.strip()

    if not safe_name:
        safe_name = "untitled_document"

    return safe_name


def _get_export_job_file_candidates(file_name: str) -> list[Path]:
    """取得可能的 export job state 檔案路徑。"""

    safe_name = _safe_file_name(file_name)
    export_jobs_dir = OUTPUT_DIR / "export_jobs"

    candidates = [
        export_jobs_dir / f"{safe_name}_detailed_notion_export_state.json",
        export_jobs_dir / f"{safe_name}.json",
    ]

    if export_jobs_dir.exists():
        candidates.extend(export_jobs_dir.glob(f"{safe_name}*.json"))

    unique_candidates = []

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
        return path.stat().st_size

    total_size = 0

    for item in path.rglob("*"):
        if item.is_file():
            total_size += item.stat().st_size

    return total_size


def _format_bytes(size_bytes: int) -> str:
    """將 bytes 轉成可讀格式。"""

    if size_bytes < 1024:
        return f"{size_bytes} B"

    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.2f} KB"

    if size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.2f} MB"

    return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


def get_document_by_file_hash(file_hash: str) -> Optional[Document]:
    """依照檔案 hash 取得文件。"""

    with get_database_session() as session:
        statement = select(Document).where(Document.file_hash == file_hash)
        return session.execute(statement).scalars().first()


def create_or_update_document(
    file_name: str,
    file_extension: str,
    file_size_bytes: int,
    file_hash: str,
    metadata: dict,
    chapters: list[dict],
) -> Document:
    """建立或更新文件與章節資料。"""

    with get_database_session() as session:
        statement = select(Document).where(Document.file_hash == file_hash)
        document = session.execute(statement).scalars().first()

        now = datetime.utcnow()

        if document is None:
            document_data = {
                "file_name": file_name,
                "file_extension": file_extension,
                "file_size_bytes": file_size_bytes,
                "file_hash": file_hash,
                "page_count": metadata.get("page_count"),
                "character_count": metadata.get("character_count", 0),
                "paragraph_count": metadata.get("paragraph_count", 0),
                "status": "analyzed",
                "export_status": "pending",
                "created_at": now,
                "updated_at": now,
            }

            document_data = _maybe_add_id(Document, document_data)

            document = Document(
                **_filter_model_kwargs(
                    Document,
                    document_data,
                )
            )

            session.add(document)
            session.flush()

        else:
            _safe_setattr(document, "file_name", file_name)
            _safe_setattr(document, "file_extension", file_extension)
            _safe_setattr(document, "file_size_bytes", file_size_bytes)
            _safe_setattr(document, "page_count", metadata.get("page_count"))
            _safe_setattr(
                document,
                "character_count",
                metadata.get("character_count", 0),
            )
            _safe_setattr(
                document,
                "paragraph_count",
                metadata.get("paragraph_count", 0),
            )
            _safe_setattr(document, "status", "analyzed")
            _safe_setattr(document, "updated_at", now)

            session.query(Chapter).filter(
                Chapter.document_id == document.id
            ).delete(synchronize_session=False)

            session.flush()

        for index, chapter in enumerate(chapters, start=1):
            source_chapter_id = str(chapter.get("chapter_id") or index)
            chapter_content = chapter.get("content", "") or ""

            chapter_data = {
                "document_id": document.id,
                "source_chapter_id": source_chapter_id,
                "chapter_order": index,
                "title": chapter.get("title", f"Module {index}"),
                "source": chapter.get("source", ""),
                "start_index": chapter.get("start_index"),
                "end_index": chapter.get("end_index"),
                "character_count": len(chapter_content),
                "subsection_count": len(chapter.get("subsections", [])),
                "export_status": "pending",
                "visual_cache_status": "pending",
                "note_cache_status": "pending",
                "notion_page_id": None,
                "notion_page_url": None,
                "created_at": now,
                "updated_at": now,
            }

            chapter_data = _maybe_add_id(Chapter, chapter_data)

            chapter_record = Chapter(
                **_filter_model_kwargs(
                    Chapter,
                    chapter_data,
                )
            )

            session.add(chapter_record)

        session.commit()
        session.refresh(document)

        return document


def list_documents() -> list[Document]:
    """列出所有文件。"""

    with get_database_session() as session:
        statement = (
            select(Document)
            .options(selectinload(Document.chapters))
            .order_by(Document.updated_at.desc())
        )

        documents = session.execute(statement).scalars().all()

        for document in documents:
            session.expunge(document)

        return documents


def get_document_with_chapters(document_id: int | str) -> Optional[Document]:
    """取得文件與章節。"""

    with get_database_session() as session:
        statement = (
            select(Document)
            .where(Document.id == document_id)
            .options(selectinload(Document.chapters))
        )

        document = session.execute(statement).scalars().first()

        if document:
            session.expunge(document)

        return document


def mark_document_exporting(document_id: int | str) -> None:
    """標記文件正在匯出。"""

    with get_database_session() as session:
        document = session.get(Document, document_id)

        if document is None:
            return

        _safe_setattr(document, "export_status", "exporting")
        _safe_setattr(document, "updated_at", datetime.utcnow())

        session.commit()


def _find_chapter_record(
    session,
    document_id: int | str,
    source_chapter_id: str,
) -> Optional[Chapter]:
    """尋找指定文件下的章節。"""

    column_names = _get_model_column_names(Chapter)

    if "source_chapter_id" in column_names:
        statement = select(Chapter).where(
            Chapter.document_id == document_id,
            Chapter.source_chapter_id == str(source_chapter_id),
        )

    elif "chapter_order" in column_names:
        try:
            chapter_order = int(source_chapter_id)
        except ValueError:
            chapter_order = 1

        statement = select(Chapter).where(
            Chapter.document_id == document_id,
            Chapter.chapter_order == chapter_order,
        )

    else:
        statement = select(Chapter).where(
            Chapter.document_id == document_id,
        )

    return session.execute(statement).scalars().first()


def update_document_export_result(
    document_id: int | str,
    export_result: dict,
) -> None:
    """依照 Notion 匯出結果更新文件與章節狀態。"""

    with get_database_session() as session:
        document = session.get(Document, document_id)

        if document is None:
            return

        completed_chapters = export_result.get("completed_chapters", [])
        failed_chapters = export_result.get("failed_chapters", [])

        completed_ids = {
            str(item.get("chapter_id"))
            for item in completed_chapters
        }

        failed_ids = {
            str(item.get("chapter_id"))
            for item in failed_chapters
        }

        for item in completed_chapters:
            chapter = _find_chapter_record(
                session=session,
                document_id=document_id,
                source_chapter_id=str(item.get("chapter_id") or item.get("chapter_order") or 1),
            )

            if chapter:
                _safe_setattr(chapter, "export_status", "completed")
                _safe_setattr(
                    chapter,
                    "notion_page_id",
                    item.get("notion_page_id"),
                )
                _safe_setattr(
                    chapter,
                    "notion_page_url",
                    item.get("notion_page_url"),
                )
                _safe_setattr(chapter, "updated_at", datetime.utcnow())

        for item in failed_chapters:
            chapter = _find_chapter_record(
                session=session,
                document_id=document_id,
                source_chapter_id=str(item.get("chapter_id") or item.get("chapter_order") or 1),
            )

            if chapter:
                _safe_setattr(chapter, "export_status", "failed")
                _safe_setattr(chapter, "updated_at", datetime.utcnow())

        all_chapters = (
            session.query(Chapter)
            .filter(Chapter.document_id == document_id)
            .all()
        )

        if all_chapters and all(
            getattr(chapter, "export_status", "pending") == "completed"
            for chapter in all_chapters
        ):
            _safe_setattr(document, "export_status", "completed")

        elif failed_ids:
            _safe_setattr(document, "export_status", "failed")

        elif completed_ids:
            _safe_setattr(document, "export_status", "partial")

        else:
            _safe_setattr(document, "export_status", "pending")

        _safe_setattr(document, "updated_at", datetime.utcnow())

        session.commit()



def _normalize_learning_text(value) -> str:
    """
    正規化 Quiz / Flash Card 比對文字。

    用途：
    - 忽略大小寫
    - 忽略多餘空白與換行
    - 忽略常見全形／半形標點差異
    """

    text = str(value or "").strip().lower()

    replacements = {
        "（": "(",
        "）": ")",
        "，": ",",
        "。": ".",
        "：": ":",
        "；": ";",
        "？": "?",
        "！": "!",
        "、": ",",
        "　": " ",
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    text = re.sub(r"\s+", "", text)
    text = re.sub(
        r"[`'\"“”‘’]",
        "",
        text,
    )

    return text


def _quiz_identity(
    question,
    answer,
) -> str:
    """建立 Quiz 去重識別鍵。"""

    normalized_question = (
        _normalize_learning_text(
            question
        )
    )

    normalized_answer = (
        _normalize_learning_text(
            answer
        )
    )

    return (
        f"{normalized_question}|"
        f"{normalized_answer}"
    )


def _flashcard_identity(
    front,
    back,
) -> str:
    """建立 Flash Card 去重識別鍵。"""

    normalized_front = (
        _normalize_learning_text(
            front
        )
    )

    normalized_back = (
        _normalize_learning_text(
            back
        )
    )

    return (
        f"{normalized_front}|"
        f"{normalized_back}"
    )


def _prepare_unique_quiz_items(
    chapter_note,
) -> tuple[list[dict], int]:
    """
    整理並去除同一批章節筆記內的重複 Quiz。

    回傳：
    - 唯一 Quiz 資料
    - 批次內被略過的重複／空白數量
    """

    unique_items: list[dict] = []
    seen_keys: set[str] = set()
    skipped_count = 0

    for quiz_item in getattr(
        chapter_note,
        "quiz",
        [],
    ):
        question = str(
            getattr(
                quiz_item,
                "question",
                "",
            )
            or ""
        ).strip()

        answer = str(
            getattr(
                quiz_item,
                "answer",
                "",
            )
            or ""
        ).strip()

        explanation = str(
            getattr(
                quiz_item,
                "explanation",
                "",
            )
            or ""
        ).strip()

        if not question or not answer:
            skipped_count += 1
            continue

        identity = _quiz_identity(
            question,
            answer,
        )

        if (
            not identity.replace("|", "")
            or identity in seen_keys
        ):
            skipped_count += 1
            continue

        seen_keys.add(
            identity
        )

        unique_items.append(
            {
                "question": question,
                "answer": answer,
                "explanation": explanation,
                "identity": identity,
            }
        )

    return unique_items, skipped_count


def _prepare_unique_flashcard_items(
    chapter_note,
) -> tuple[list[dict], int]:
    """
    整理並去除同一批章節筆記內的重複 Flash Cards。

    回傳：
    - 唯一卡片資料
    - 批次內被略過的重複／空白數量
    """

    unique_items: list[dict] = []
    seen_keys: set[str] = set()
    skipped_count = 0

    for flashcard_item in getattr(
        chapter_note,
        "flashcards",
        [],
    ):
        front = str(
            getattr(
                flashcard_item,
                "front",
                "",
            )
            or ""
        ).strip()

        back = str(
            getattr(
                flashcard_item,
                "back",
                "",
            )
            or ""
        ).strip()

        if not front or not back:
            skipped_count += 1
            continue

        identity = _flashcard_identity(
            front,
            back,
        )

        if (
            not identity.replace("|", "")
            or identity in seen_keys
        ):
            skipped_count += 1
            continue

        seen_keys.add(
            identity
        )

        unique_items.append(
            {
                "front": front,
                "back": back,
                "identity": identity,
            }
        )

    return unique_items, skipped_count


def save_chapter_learning_items(
    document_id: int | str,
    source_chapter_id: str,
    chapter_note,
) -> dict:
    """
    將章節 Quiz / Flash Cards 安全寫入 SQLite。

    防護：
    - 不刪除既有 QuizAttempt / FlashcardReview
    - 同一批快取先自行去重
    - 與資料庫現有資料做正規化比對
    - 只新增真正缺少的項目
    - 整章使用單一 transaction，失敗時全部 rollback
    """

    with get_database_session() as session:
        try:
            chapter = _find_chapter_record(
                session=session,
                document_id=document_id,
                source_chapter_id=str(
                    source_chapter_id
                ),
            )

            if chapter is None:
                return {
                    "saved": False,
                    "reason": "找不到對應章節",
                    "quiz_count": 0,
                    "flashcard_count": 0,
                    "added_quiz_count": 0,
                    "added_flashcard_count": 0,
                    "skipped_quiz_count": 0,
                    "skipped_flashcard_count": 0,
                }

            (
                prepared_quizzes,
                batch_skipped_quizzes,
            ) = _prepare_unique_quiz_items(
                chapter_note
            )

            (
                prepared_flashcards,
                batch_skipped_flashcards,
            ) = _prepare_unique_flashcard_items(
                chapter_note
            )

            existing_quizzes = (
                session.query(Quiz)
                .filter(
                    Quiz.document_id
                    == document_id,
                    Quiz.chapter_id
                    == chapter.id,
                )
                .all()
            )

            existing_quiz_keys = {
                _quiz_identity(
                    getattr(
                        quiz,
                        "question",
                        "",
                    ),
                    (
                        getattr(
                            quiz,
                            "correct_answer",
                            None,
                        )
                        or getattr(
                            quiz,
                            "answer",
                            "",
                        )
                    ),
                )
                for quiz in existing_quizzes
            }

            existing_flashcards = (
                session.query(Flashcard)
                .filter(
                    Flashcard.document_id
                    == document_id,
                    Flashcard.chapter_id
                    == chapter.id,
                )
                .all()
            )

            existing_flashcard_keys = {
                _flashcard_identity(
                    getattr(
                        flashcard,
                        "front",
                        "",
                    ),
                    getattr(
                        flashcard,
                        "back",
                        "",
                    ),
                )
                for flashcard in existing_flashcards
            }

            now = datetime.utcnow()

            added_quiz_count = 0
            skipped_quiz_count = (
                batch_skipped_quizzes
            )

            for item in prepared_quizzes:
                identity = item["identity"]

                if identity in existing_quiz_keys:
                    skipped_quiz_count += 1
                    continue

                quiz_data = {
                    "document_id": document_id,
                    "chapter_id": chapter.id,
                    "question": item[
                        "question"
                    ],
                    "correct_answer": item[
                        "answer"
                    ],
                    "answer": item["answer"],
                    "explanation": item[
                        "explanation"
                    ],
                    "difficulty": "medium",
                    "created_at": now,
                    "updated_at": now,
                }

                quiz_data = _maybe_add_id(
                    Quiz,
                    quiz_data,
                )

                session.add(
                    Quiz(
                        **_filter_model_kwargs(
                            Quiz,
                            quiz_data,
                        )
                    )
                )

                existing_quiz_keys.add(
                    identity
                )

                added_quiz_count += 1

            added_flashcard_count = 0
            skipped_flashcard_count = (
                batch_skipped_flashcards
            )

            for item in prepared_flashcards:
                identity = item["identity"]

                if identity in (
                    existing_flashcard_keys
                ):
                    skipped_flashcard_count += 1
                    continue

                flashcard_data = {
                    "document_id": document_id,
                    "chapter_id": chapter.id,
                    "front": item["front"],
                    "back": item["back"],
                    "created_at": now,
                    "updated_at": now,
                }

                flashcard_data = _maybe_add_id(
                    Flashcard,
                    flashcard_data,
                )

                session.add(
                    Flashcard(
                        **_filter_model_kwargs(
                            Flashcard,
                            flashcard_data,
                        )
                    )
                )

                existing_flashcard_keys.add(
                    identity
                )

                added_flashcard_count += 1

            _safe_setattr(
                chapter,
                "note_cache_status",
                "completed",
            )

            _safe_setattr(
                chapter,
                "updated_at",
                now,
            )

            session.flush()
            session.commit()

            total_quiz_count = (
                session.query(
                    func.count(Quiz.id)
                )
                .filter(
                    Quiz.document_id
                    == document_id,
                    Quiz.chapter_id
                    == chapter.id,
                )
                .scalar()
                or 0
            )

            total_flashcard_count = (
                session.query(
                    func.count(
                        Flashcard.id
                    )
                )
                .filter(
                    Flashcard.document_id
                    == document_id,
                    Flashcard.chapter_id
                    == chapter.id,
                )
                .scalar()
                or 0
            )

            return {
                "saved": True,
                "reason": "",
                "quiz_count": int(
                    total_quiz_count
                ),
                "flashcard_count": int(
                    total_flashcard_count
                ),
                "added_quiz_count": (
                    added_quiz_count
                ),
                "added_flashcard_count": (
                    added_flashcard_count
                ),
                "skipped_quiz_count": (
                    skipped_quiz_count
                ),
                "skipped_flashcard_count": (
                    skipped_flashcard_count
                ),
            }

        except Exception as error:
            session.rollback()

            return {
                "saved": False,
                "reason": (
                    "SQLite 章節學習資料寫入失敗："
                    f"{error}"
                ),
                "quiz_count": 0,
                "flashcard_count": 0,
                "added_quiz_count": 0,
                "added_flashcard_count": 0,
                "skipped_quiz_count": 0,
                "skipped_flashcard_count": 0,
            }


def count_chapter_learning_items(
    document_id: int | str,
    source_chapter_id: str,
) -> dict:
    """統計單一章節的 Quiz / Flash Cards 數量。"""

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


def count_document_learning_items(document_id: int | str) -> dict:
    """統計整份文件的 Quiz / Flash Cards 數量。"""

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

        return {
            "quiz_count": quiz_count or 0,
            "flashcard_count": flashcard_count or 0,
        }


def get_document_storage_usage(document_id: int | str) -> dict:
    """估算文件相關本機資料佔用空間。"""

    with get_database_session() as session:
        document = session.get(Document, document_id)

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

        cache_dir = _get_chapter_cache_dir(file_name)
        cache_size = _get_path_size(cache_dir)

        export_state_size = 0

        for path in _get_export_job_file_candidates(file_name):
            export_state_size += _get_path_size(path)

        approximate_database_size = (
            int(getattr(document, "file_size_bytes", 0) or 0)
            + int(getattr(document, "character_count", 0) or 0)
            + chapter_count * 1024
            + quiz_count * 2048
            + flashcard_count * 1024
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
            "database_size_bytes": approximate_database_size,
            "cache_size_bytes": cache_size,
            "export_state_size_bytes": export_state_size,
            "total_size_bytes": total_size,
            "database_size_text": _format_bytes(approximate_database_size),
            "cache_size_text": _format_bytes(cache_size),
            "export_state_size_text": _format_bytes(export_state_size),
            "total_size_text": _format_bytes(total_size),
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

    deleted_files = []
    deleted_dirs = []

    with get_database_session() as session:
        document = session.get(Document, document_id)

        if document is None:
            return {
                "deleted": False,
                "reason": "找不到文件",
                "deleted_files": [],
                "deleted_dirs": [],
            }

        file_name = document.file_name

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
            session.query(QuizAttempt).filter(
                QuizAttempt.quiz_id.in_(quiz_ids)
            ).delete(synchronize_session=False)

        if flashcard_ids:
            session.query(FlashcardReview).filter(
                FlashcardReview.flashcard_id.in_(flashcard_ids)
            ).delete(synchronize_session=False)

            session.query(ReviewSchedule).filter(
                (
                    ReviewSchedule.item_type == "flashcard"
                )
                & ReviewSchedule.item_id.in_(flashcard_ids)
            ).delete(synchronize_session=False)

        session.query(Quiz).filter(
            Quiz.document_id == document_id
        ).delete(synchronize_session=False)

        session.query(Flashcard).filter(
            Flashcard.document_id == document_id
        ).delete(synchronize_session=False)

        session.query(Chapter).filter(
            Chapter.document_id == document_id
        ).delete(synchronize_session=False)

        session.delete(document)
        session.commit()

    if delete_cache:
        cache_dir = _get_chapter_cache_dir(file_name)

        if cache_dir.exists():
            shutil.rmtree(cache_dir)
            deleted_dirs.append(str(cache_dir))

    if delete_export_state:
        for path in _get_export_job_file_candidates(file_name):
            if path.exists() and path.is_file():
                path.unlink()
                deleted_files.append(str(path))

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

    data = []

    for document in documents:
        data.append(
            {
                "id": getattr(document, "id", ""),
                "file_name": getattr(document, "file_name", ""),
                "file_extension": getattr(document, "file_extension", ""),
                "file_size_bytes": getattr(document, "file_size_bytes", 0),
                "status": getattr(document, "status", "pending"),
                "export_status": getattr(document, "export_status", "pending"),
                "chapter_count": len(getattr(document, "chapters", []) or []),
                "created_at": str(getattr(document, "created_at", "")),
                "updated_at": str(getattr(document, "updated_at", "")),
            }
        )

    return json.dumps(data, ensure_ascii=False, indent=2)