from __future__ import annotations

import unittest
from datetime import datetime
from types import SimpleNamespace

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.database.database import Base
from src.database.models import (
    Chapter,
    Document,
    Flashcard,
    FlashcardReview,
    Quiz,
    QuizAttempt,
)
from src.services import learning_data_admin_service as admin_service
from src.services import learning_database_service as database_service
from src.services.learning_item_identity import (
    flashcard_identity,
    quiz_identity,
)


class LearningDataStabilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )

        @event.listens_for(self.engine, "connect")
        def _enable_foreign_keys(connection, _record) -> None:
            cursor = connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(
            bind=self.engine,
            expire_on_commit=False,
        )
        self.original_database_session = database_service.get_database_session
        self.original_admin_session = admin_service.get_database_session
        database_service.get_database_session = self.session_factory
        admin_service.get_database_session = self.session_factory

        with self.session_factory() as session:
            session.add(
                Document(
                    id="document-1",
                    file_name="test.pdf",
                    file_extension=".pdf",
                    file_hash="test-hash",
                )
            )
            session.add(
                Chapter(
                    id="chapter-1",
                    document_id="document-1",
                    source_chapter_id="1",
                    chapter_order=1,
                    title="第一章",
                )
            )
            session.commit()

    def tearDown(self) -> None:
        database_service.get_database_session = self.original_database_session
        admin_service.get_database_session = self.original_admin_session
        self.engine.dispose()

    def _chapter_note(self) -> SimpleNamespace:
        return SimpleNamespace(
            quiz=[
                SimpleNamespace(
                    question="Python 的 list 可以修改嗎？",
                    answer="可以",
                    explanation="list 是 mutable。",
                ),
                SimpleNamespace(
                    question="Python的 list 可以修改嗎?",
                    answer="可以",
                    explanation="重複題",
                ),
            ],
            flashcards=[
                SimpleNamespace(front="什麼是 list？", back="可變序列"),
                SimpleNamespace(front="什麼是list?", back="可變序列"),
            ],
        )

    def test_identity_normalizes_formatting_differences(self) -> None:
        self.assertEqual(
            quiz_identity("問題？", "答 案"),
            quiz_identity("問題?", "答案"),
        )
        self.assertEqual(
            flashcard_identity("正面：A", "背面 B"),
            flashcard_identity("正面:A", "背面B"),
        )

    def test_cache_sync_is_idempotent_and_preserves_history(self) -> None:
        first = database_service.save_chapter_learning_items(
            "document-1",
            "1",
            self._chapter_note(),
        )
        self.assertTrue(first["saved"])
        self.assertEqual(first["added_quiz_count"], 1)
        self.assertEqual(first["added_flashcard_count"], 1)

        with self.session_factory() as session:
            quiz = session.query(Quiz).one()
            card = session.query(Flashcard).one()
            session.add(
                QuizAttempt(
                    quiz_id=quiz.id,
                    user_answer="可以",
                    self_rating="correct",
                    score=2,
                    is_correct=True,
                )
            )
            session.add(
                FlashcardReview(
                    flashcard_id=card.id,
                    familiarity_score=4,
                )
            )
            session.commit()

        second = database_service.save_chapter_learning_items(
            "document-1",
            "1",
            self._chapter_note(),
        )
        self.assertTrue(second["saved"])
        self.assertEqual(second["added_quiz_count"], 0)
        self.assertEqual(second["added_flashcard_count"], 0)

        with self.session_factory() as session:
            self.assertEqual(session.query(Quiz).count(), 1)
            self.assertEqual(session.query(Flashcard).count(), 1)
            self.assertEqual(session.query(QuizAttempt).count(), 1)
            self.assertEqual(session.query(FlashcardReview).count(), 1)

    def test_duplicate_cleanup_reassigns_history(self) -> None:
        with self.session_factory() as session:
            quiz_1 = Quiz(
                id="quiz-1",
                document_id="document-1",
                chapter_id="chapter-1",
                question="重複題？",
                correct_answer="答案",
                created_at=datetime(2025, 1, 1),
            )
            quiz_2 = Quiz(
                id="quiz-2",
                document_id="document-1",
                chapter_id="chapter-1",
                question="重複題?",
                correct_answer="答 案",
                created_at=datetime(2025, 1, 2),
            )
            card_1 = Flashcard(
                id="card-1",
                document_id="document-1",
                chapter_id="chapter-1",
                front="正面",
                back="背面",
                created_at=datetime(2025, 1, 1),
            )
            card_2 = Flashcard(
                id="card-2",
                document_id="document-1",
                chapter_id="chapter-1",
                front="正 面",
                back="背 面",
                created_at=datetime(2025, 1, 2),
            )
            session.add_all([quiz_1, quiz_2, card_1, card_2])
            session.flush()
            session.add(
                QuizAttempt(
                    quiz_id="quiz-2",
                    user_answer="答案",
                    self_rating="correct",
                    score=2,
                    is_correct=True,
                )
            )
            session.add(
                FlashcardReview(
                    flashcard_id="card-2",
                    familiarity_score=5,
                )
            )
            session.commit()

        preview = admin_service.deduplicate_document_learning_items(
            "document-1",
            preview_only=True,
        )
        self.assertEqual(preview["duplicate_quiz_count"], 1)
        self.assertEqual(preview["duplicate_flashcard_count"], 1)

        result = admin_service.deduplicate_document_learning_items(
            "document-1",
            preview_only=False,
        )
        self.assertEqual(result["merged_quiz_count"], 1)
        self.assertEqual(result["merged_flashcard_count"], 1)

        with self.session_factory() as session:
            self.assertEqual(session.query(Quiz).count(), 1)
            self.assertEqual(session.query(Flashcard).count(), 1)
            self.assertEqual(session.query(QuizAttempt).count(), 1)
            self.assertEqual(session.query(FlashcardReview).count(), 1)
            self.assertEqual(
                session.query(QuizAttempt).one().quiz_id,
                session.query(Quiz).one().id,
            )
            self.assertEqual(
                session.query(FlashcardReview).one().flashcard_id,
                session.query(Flashcard).one().id,
            )

    def test_reanalysis_preserves_matching_chapter_and_learning_history(self) -> None:
        database_service.save_chapter_learning_items(
            "document-1",
            "1",
            self._chapter_note(),
        )

        with self.session_factory() as session:
            original_chapter_id = session.query(Chapter).one().id
            quiz = session.query(Quiz).one()
            card = session.query(Flashcard).one()
            session.add(
                QuizAttempt(
                    quiz_id=quiz.id,
                    user_answer="可以",
                    self_rating="correct",
                    score=2,
                    is_correct=True,
                )
            )
            session.add(
                FlashcardReview(
                    flashcard_id=card.id,
                    familiarity_score=4,
                )
            )
            session.commit()

        database_service.create_or_update_document(
            file_name="test.pdf",
            file_extension=".pdf",
            file_size_bytes=100,
            file_hash="test-hash",
            metadata={"page_count": 1, "character_count": 20},
            chapters=[
                {
                    "chapter_id": "1",
                    "title": "更新後的第一章",
                    "content": "更新後內容",
                }
            ],
        )

        with self.session_factory() as session:
            chapter = session.query(Chapter).one()
            self.assertEqual(chapter.id, original_chapter_id)
            self.assertEqual(chapter.title, "更新後的第一章")
            self.assertEqual(session.query(Quiz).count(), 1)
            self.assertEqual(session.query(Flashcard).count(), 1)
            self.assertEqual(session.query(QuizAttempt).count(), 1)
            self.assertEqual(session.query(FlashcardReview).count(), 1)

    def test_export_result_accepts_string_chapter_items(self) -> None:
        database_service.update_document_export_result(
            "document-1",
            {
                "completed_chapters": ["1"],
                "failed_chapters": ["1"],
            },
        )

        with self.session_factory() as session:
            document = session.get(Document, "document-1")
            chapter = session.get(Chapter, "chapter-1")

            self.assertEqual(document.export_status, "completed")
            self.assertEqual(chapter.export_status, "completed")


if __name__ == "__main__":
    unittest.main()
