from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.database.database import Base
from src.services import background_job_service as job_service


class BackgroundJobServiceTests(unittest.TestCase):
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
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.original_session = job_service.get_database_session
        self.original_job_root = job_service.JOB_ROOT
        job_service.get_database_session = self.session_factory
        job_service.JOB_ROOT = Path(self.temporary_directory.name)

    def tearDown(self) -> None:
        job_service.get_database_session = self.original_session
        job_service.JOB_ROOT = self.original_job_root
        self.temporary_directory.cleanup()
        self.engine.dispose()

    def test_payload_result_and_progress_round_trip(self) -> None:
        job = job_service.create_background_job(
            job_type="notion_export",
            display_name="測試匯出",
            payload={
                "document_name": "test.pdf",
                "parsed_document": {"pdf_bytes": b"pdf-data"},
            },
            document_id="document-1",
        )

        payload = job_service.load_background_job_payload(job["id"])
        self.assertEqual(payload["parsed_document"]["pdf_bytes"], b"pdf-data")

        claimed = job_service.claim_next_background_job()
        self.assertEqual(claimed["id"], job["id"])
        self.assertEqual(claimed["status"], "running")

        job_service.update_background_job_progress(
            job["id"],
            current=2,
            total=4,
            message="完成第二章",
        )
        progress = job_service.get_background_job(job["id"])
        self.assertEqual(progress["progress_percent"], 50)

        job_service.save_background_job_result(
            job["id"],
            {"completed_chapters": ["1", "2"]},
        )
        completed = job_service.get_background_job(job["id"])
        self.assertEqual(completed["status"], "completed")
        self.assertEqual(
            job_service.load_background_job_result(job["id"]),
            {"completed_chapters": ["1", "2"]},
        )

    def test_pending_job_can_be_cancelled_before_claim(self) -> None:
        job = job_service.create_background_job(
            job_type="document_analysis",
            display_name="測試分析",
            payload={"chunks": [{"chunk_id": 1, "content": "test"}]},
        )

        self.assertTrue(job_service.request_background_job_cancel(job["id"]))
        claimed = job_service.claim_next_background_job()
        self.assertEqual(claimed["status"], "cancelled")
        self.assertIsNone(job_service.claim_next_background_job())

    def test_only_terminal_jobs_can_be_deleted(self) -> None:
        job = job_service.create_background_job(
            job_type="document_analysis",
            display_name="測試刪除",
            payload={"chunks": [{"chunk_id": 1, "content": "test"}]},
        )
        self.assertFalse(job_service.delete_background_job(job["id"]))
        job_service.request_background_job_cancel(job["id"])
        job_service.claim_next_background_job()
        self.assertTrue(job_service.delete_background_job(job["id"]))
        self.assertIsNone(job_service.get_background_job(job["id"]))

    def test_running_jobs_are_recovered_after_worker_restart(self) -> None:
        job = job_service.create_background_job(
            job_type="document_analysis",
            display_name="測試恢復",
            payload={"chunks": [{"chunk_id": 1, "content": "test"}]},
        )
        claimed = job_service.claim_next_background_job()
        self.assertEqual(claimed["id"], job["id"])
        self.assertEqual(claimed["status"], "running")

        recovered_count = job_service.recover_interrupted_background_jobs()

        self.assertEqual(recovered_count, 1)
        recovered = job_service.get_background_job(job["id"])
        self.assertEqual(recovered["status"], "pending")
        self.assertIn("重新排入", recovered["progress_message"])


if __name__ == "__main__":
    unittest.main()
