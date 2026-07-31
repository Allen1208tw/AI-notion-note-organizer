from __future__ import annotations

import unittest
from unittest.mock import patch

import background_worker
from src.services import chapter_notion_service


class NotionExportFailureTests(unittest.TestCase):
    def test_worker_rejects_incomplete_notion_export_result(self) -> None:
        incomplete_result = {
            "is_finished": False,
            "completed_chapter_count": 0,
            "failed_this_run": [
                {
                    "chapter_id": "1",
                    "error": "429 RESOURCE_EXHAUSTED",
                }
            ],
        }

        with patch.object(
            background_worker,
            "create_document_learning_notebook",
            return_value=incomplete_result,
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "完成 0 / 1.*429 RESOURCE_EXHAUSTED",
            ):
                background_worker._run_notion_export(
                    "job-1",
                    {
                        "document_name": "Python 基礎.pdf",
                        "chapters": [{"chapter_id": "1", "title": "介紹"}],
                        "parsed_document": {},
                        "resume": True,
                    },
                )

    def test_gemini_quota_error_stops_after_first_failed_chapter(self) -> None:
        chapters = [
            {"chapter_id": "1", "title": "介紹"},
            {"chapter_id": "2", "title": "變數"},
        ]
        export_state = {
            "parent_page_id": "parent-page",
            "parent_page_url": "https://notion.example/parent",
            "completed_chapters": {},
            "failed_chapters": {},
        }
        quota_error = RuntimeError(
            "429 RESOURCE_EXHAUSTED: Gemini free tier quota exceeded"
        )

        with patch.object(chapter_notion_service, "_get_notion_client", return_value=object()):
            with patch.object(chapter_notion_service, "_get_ai_generation_metadata", return_value={}):
                with patch.object(chapter_notion_service, "_resolve_document_id", return_value=None):
                    with patch.object(
                        chapter_notion_service,
                        "_sync_cached_notes_to_sqlite",
                        return_value={
                            "synced_chapter_count": 0,
                            "skipped_chapter_count": 0,
                            "failed_chapter_count": 0,
                            "synced_quiz_count": 0,
                            "synced_flashcard_count": 0,
                            "errors": [],
                        },
                    ):
                        with patch.object(
                            chapter_notion_service,
                            "_safe_load_export_state",
                            return_value=export_state,
                        ):
                            with patch.object(
                                chapter_notion_service,
                                "_safe_get_pending_chapters",
                                return_value=chapters,
                            ):
                                with patch.object(
                                    chapter_notion_service,
                                    "_safe_is_chapter_completed",
                                    return_value=False,
                                ):
                                    with patch.object(
                                        chapter_notion_service,
                                        "load_chapter_cache",
                                        return_value={},
                                    ):
                                        with patch.object(
                                            chapter_notion_service,
                                            "_get_visual_context",
                                            return_value=([], False),
                                        ):
                                            with patch.object(
                                                chapter_notion_service,
                                                "_get_chapter_note",
                                                side_effect=quota_error,
                                            ) as get_note:
                                                with patch.object(
                                                    chapter_notion_service,
                                                    "_safe_mark_chapter_failed",
                                                ):
                                                    with self.assertRaisesRegex(
                                                        RuntimeError,
                                                        "Gemini.*額度",
                                                    ):
                                                        chapter_notion_service.create_document_learning_notebook(
                                                            document_name="Python 基礎.pdf",
                                                            chapters=chapters,
                                                            parsed_document={},
                                                            resume=True,
                                                        )

        self.assertEqual(get_note.call_count, 1)


if __name__ == "__main__":
    unittest.main()
