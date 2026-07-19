from __future__ import annotations

import argparse
import json
import os
import time
import traceback
from datetime import UTC, datetime

from src.config.settings import OUTPUT_DIR
from src.database.init_db import initialize_database
from src.models.analysis_models import ChunkAnalysisResult
from src.services.analysis_service import analyze_document
from src.services.background_job_service import (
    JobCancelled,
    background_job_cancel_requested,
    claim_next_background_job,
    load_background_job_payload,
    mark_background_job_cancelled,
    mark_background_job_failed,
    recover_interrupted_background_jobs,
    save_background_job_result,
    update_background_job_progress,
)
from src.services.chapter_notion_service import create_document_learning_notebook
from src.services.learning_database_service import (
    mark_document_exporting,
    update_document_export_result,
)


WORKER_STATE_FILE = OUTPUT_DIR / ".background_worker.json"


def _write_worker_state(current_job_id: str | None = None) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    WORKER_STATE_FILE.write_text(
        json.dumps(
            {
                "pid": os.getpid(),
                "current_job_id": current_job_id,
                "updated_at": datetime.now(UTC).isoformat(),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _run_document_analysis(job_id: str, payload: dict) -> dict:
    chunks = list(payload.get("chunks") or [])
    if not chunks:
        raise ValueError("背景分析工作沒有可分析的 Chunks。")

    def progress(current: int, total: int, message: str) -> None:
        update_background_job_progress(job_id, current, total, message)

    def check_cancelled() -> None:
        if background_job_cancel_requested(job_id):
            raise JobCancelled("使用者要求取消文件分析。")

    update_background_job_progress(job_id, 0, len(chunks) + 1, "準備分析文件")
    final_result, chunk_results = analyze_document(
        chunks,
        progress_callback=progress,
        cancellation_check=check_cancelled,
    )

    return {
        "final_result": final_result.model_dump(mode="python"),
        "chunk_results": [
            result.model_dump(mode="python")
            if isinstance(result, ChunkAnalysisResult)
            else result
            for result in chunk_results
        ],
    }


def _run_notion_export(job_id: str, payload: dict) -> dict:
    document_name = str(payload.get("document_name") or "").strip()
    chapters = list(payload.get("chapters") or [])
    parsed_document = dict(payload.get("parsed_document") or {})
    document_id = payload.get("document_id")
    resume = bool(payload.get("resume", False))

    if not document_name or not chapters:
        raise ValueError("Notion 背景匯出缺少文件名稱或章節。")

    if document_id:
        mark_document_exporting(str(document_id))

    def progress(current: int, total: int, message: str) -> None:
        update_background_job_progress(job_id, current, total, message)

    result = create_document_learning_notebook(
        document_name=document_name,
        chapters=chapters,
        parsed_document=parsed_document,
        progress_callback=progress,
        max_visual_pages=3,
        resume=resume,
        document_id=document_id,
    )
    if not isinstance(result, dict):
        raise TypeError("Notion 匯出結果格式錯誤，預期為 dict。")

    if document_id:
        update_document_export_result(str(document_id), result)
    return result


def _run_job(job: dict) -> None:
    job_id = str(job["id"])
    payload = load_background_job_payload(job_id)

    if job["job_type"] == "document_analysis":
        result = _run_document_analysis(job_id, payload)
    elif job["job_type"] == "notion_export":
        result = _run_notion_export(job_id, payload)
    else:
        raise ValueError(f"沒有此背景工作處理器：{job['job_type']}")

    save_background_job_result(job_id, result)


def run_worker(once: bool = False, poll_seconds: float = 1.0) -> int:
    schema_issues = initialize_database()
    if schema_issues:
        print("背景 Worker 無法啟動：SQLite Schema 需要更新。")
        return 1

    recovered_count = recover_interrupted_background_jobs()
    if recovered_count:
        print(f"已恢復 {recovered_count} 個上次中斷的背景工作。")

    try:
        while True:
            _write_worker_state()
            job = claim_next_background_job()
            if job is None:
                if once:
                    return 0
                time.sleep(max(float(poll_seconds), 0.2))
                continue

            job_id = str(job["id"])
            if job["status"] == "cancelled":
                if once:
                    return 0
                continue

            _write_worker_state(job_id)
            try:
                _run_job(job)
            except JobCancelled:
                mark_background_job_cancelled(job_id)
            except Exception as error:
                traceback.print_exc()
                mark_background_job_failed(job_id, error)

            if once:
                return 0
    finally:
        try:
            WORKER_STATE_FILE.unlink(missing_ok=True)
        except OSError:
            pass


def main() -> int:
    parser = argparse.ArgumentParser(description="AI Notion 背景工作 Worker")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--poll-seconds", type=float, default=1.0)
    args = parser.parse_args()
    return run_worker(once=args.once, poll_seconds=args.poll_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
