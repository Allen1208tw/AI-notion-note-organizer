from __future__ import annotations

import json
import shutil
import uuid
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel
from sqlalchemy import select

from src.config.settings import OUTPUT_DIR
from src.database.database import get_database_session
from src.database.models import BackgroundJob


JOB_ROOT = OUTPUT_DIR / "background_jobs"
TERMINAL_STATUSES = {"completed", "failed", "cancelled"}
ACTIVE_STATUSES = {"pending", "running"}
SUPPORTED_JOB_TYPES = {"document_analysis", "notion_export"}


class JobCancelled(RuntimeError):
    """背景工作收到使用者取消要求。"""


def _utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _job_dir(job_id: str) -> Path:
    return JOB_ROOT / job_id


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    temporary_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary_path.replace(path)


def _encode_value(value: Any, assets_dir: Path, counter: list[int]) -> Any:
    if isinstance(value, BaseModel):
        return _encode_value(value.model_dump(mode="python"), assets_dir, counter)

    if isinstance(value, bytes):
        asset_name = f"binary_{counter[0]:04d}.bin"
        counter[0] += 1
        assets_dir.mkdir(parents=True, exist_ok=True)
        (assets_dir / asset_name).write_bytes(value)
        return {"__background_job_binary__": asset_name}

    if isinstance(value, Path):
        return {"__background_job_path__": str(value)}

    if isinstance(value, datetime):
        return {"__background_job_datetime__": value.isoformat()}

    if isinstance(value, date):
        return {"__background_job_date__": value.isoformat()}

    if isinstance(value, dict):
        return {
            str(key): _encode_value(item, assets_dir, counter)
            for key, item in value.items()
        }

    if isinstance(value, (list, tuple, set)):
        return [_encode_value(item, assets_dir, counter) for item in value]

    if value is None or isinstance(value, (str, int, float, bool)):
        return value

    raise TypeError(f"背景工作資料不支援此型別：{type(value).__name__}")


def _decode_value(value: Any, assets_dir: Path) -> Any:
    if isinstance(value, list):
        return [_decode_value(item, assets_dir) for item in value]

    if not isinstance(value, dict):
        return value

    if set(value) == {"__background_job_binary__"}:
        asset_name = Path(str(value["__background_job_binary__"])).name
        asset_path = (assets_dir / asset_name).resolve()
        if assets_dir.resolve() not in asset_path.parents:
            raise ValueError("背景工作二進位檔案路徑不合法。")
        return asset_path.read_bytes()

    if set(value) == {"__background_job_path__"}:
        return Path(str(value["__background_job_path__"]))

    if set(value) == {"__background_job_datetime__"}:
        return datetime.fromisoformat(str(value["__background_job_datetime__"]))

    if set(value) == {"__background_job_date__"}:
        return date.fromisoformat(str(value["__background_job_date__"]))

    return {
        key: _decode_value(item, assets_dir)
        for key, item in value.items()
    }


def _serialize_to_job_file(job_id: str, name: str, value: Any) -> Path:
    directory = _job_dir(job_id)
    path = directory / f"{name}.json"
    encoded = _encode_value(value, directory / f"{name}_assets", [0])
    _write_json(path, encoded)
    return path


def _load_job_file(job_id: str, path_value: str) -> Any:
    path = Path(path_value)
    if not path.is_absolute():
        path = _job_dir(job_id) / path
    path = path.resolve()
    directory = _job_dir(job_id).resolve()
    if directory != path.parent and directory not in path.parents:
        raise ValueError("背景工作檔案不在允許的資料夾內。")
    raw = json.loads(path.read_text(encoding="utf-8"))
    return _decode_value(raw, path.parent / f"{path.stem}_assets")


def _job_to_dict(job: BackgroundJob) -> dict:
    total = max(int(job.progress_total or 1), 1)
    current = min(max(int(job.progress_current or 0), 0), total)
    return {
        "id": job.id,
        "job_type": job.job_type,
        "status": job.status,
        "document_id": job.document_id,
        "display_name": job.display_name,
        "progress_current": current,
        "progress_total": total,
        "progress_percent": int((current / total) * 100),
        "progress_message": job.progress_message,
        "error_message": job.error_message,
        "cancel_requested": bool(job.cancel_requested),
        "created_at": job.created_at,
        "started_at": job.started_at,
        "finished_at": job.finished_at,
        "updated_at": job.updated_at,
    }


def create_background_job(
    job_type: str,
    display_name: str,
    payload: dict,
    document_id: Optional[str] = None,
) -> dict:
    if job_type not in SUPPORTED_JOB_TYPES:
        raise ValueError(f"不支援的背景工作類型：{job_type}")

    job_id = str(uuid.uuid4())
    payload_path = _serialize_to_job_file(job_id, "payload", payload)
    now = _utc_now()

    try:
        with get_database_session() as session:
            job = BackgroundJob(
                id=job_id,
                job_type=job_type,
                status="pending",
                document_id=str(document_id) if document_id else None,
                display_name=str(display_name).strip() or job_type,
                payload_path=str(payload_path),
                progress_current=0,
                progress_total=1,
                progress_message="等待背景工作處理",
                created_at=now,
                updated_at=now,
            )
            session.add(job)
            session.commit()
            session.refresh(job)
            return _job_to_dict(job)
    except Exception:
        shutil.rmtree(_job_dir(job_id), ignore_errors=True)
        raise


def get_background_job(job_id: str) -> Optional[dict]:
    with get_database_session() as session:
        job = session.get(BackgroundJob, str(job_id))
        return _job_to_dict(job) if job is not None else None


def list_background_jobs(limit: int = 100) -> list[dict]:
    safe_limit = min(max(int(limit), 1), 500)
    with get_database_session() as session:
        statement = (
            select(BackgroundJob)
            .order_by(BackgroundJob.created_at.desc())
            .limit(safe_limit)
        )
        jobs = session.execute(statement).scalars().all()
        return [_job_to_dict(job) for job in jobs]


def claim_next_background_job() -> Optional[dict]:
    with get_database_session() as session:
        statement = (
            select(BackgroundJob)
            .where(BackgroundJob.status == "pending")
            .order_by(BackgroundJob.created_at.asc())
            .limit(1)
        )
        job = session.execute(statement).scalars().first()
        if job is None:
            return None

        now = _utc_now()
        if job.cancel_requested:
            job.status = "cancelled"
            job.finished_at = now
            job.progress_message = "工作已取消"
        else:
            job.status = "running"
            job.started_at = now
            job.progress_message = "背景工作開始執行"
        job.updated_at = now
        session.commit()
        session.refresh(job)
        return _job_to_dict(job)


def recover_interrupted_background_jobs() -> int:
    """將前一個 Worker 異常中止時留下的 running 工作放回佇列。"""

    now = _utc_now()
    with get_database_session() as session:
        jobs = session.execute(
            select(BackgroundJob).where(BackgroundJob.status == "running")
        ).scalars().all()
        for job in jobs:
            if job.cancel_requested:
                job.status = "cancelled"
                job.finished_at = now
                job.progress_message = "Worker 中止後已完成取消"
            else:
                job.status = "pending"
                job.started_at = None
                job.progress_message = "偵測到上次中斷，已重新排入背景佇列"
            job.updated_at = now
        session.commit()
        return len(jobs)


def load_background_job_payload(job_id: str) -> dict:
    with get_database_session() as session:
        job = session.get(BackgroundJob, str(job_id))
        if job is None:
            raise ValueError("找不到背景工作。")
        payload_path = job.payload_path
    payload = _load_job_file(str(job_id), payload_path)
    if not isinstance(payload, dict):
        raise TypeError("背景工作 Payload 必須是 dict。")
    return payload


def save_background_job_result(job_id: str, result: Any) -> None:
    result_path = _serialize_to_job_file(str(job_id), "result", result)
    now = _utc_now()
    with get_database_session() as session:
        job = session.get(BackgroundJob, str(job_id))
        if job is None:
            raise ValueError("找不到背景工作。")
        job.result_path = str(result_path)
        job.status = "completed"
        job.progress_current = max(job.progress_total, 1)
        job.progress_message = "背景工作已完成"
        job.error_message = None
        job.finished_at = now
        job.updated_at = now
        session.commit()


def load_background_job_result(job_id: str) -> Any:
    with get_database_session() as session:
        job = session.get(BackgroundJob, str(job_id))
        if job is None:
            raise ValueError("找不到背景工作。")
        if job.status != "completed" or not job.result_path:
            raise ValueError("背景工作尚未完成，沒有可讀取的結果。")
        result_path = job.result_path
    return _load_job_file(str(job_id), result_path)


def update_background_job_progress(
    job_id: str,
    current: int,
    total: int,
    message: str,
) -> None:
    safe_total = max(int(total or 1), 1)
    safe_current = min(max(int(current or 0), 0), safe_total)
    with get_database_session() as session:
        job = session.get(BackgroundJob, str(job_id))
        if job is None:
            raise ValueError("找不到背景工作。")
        if job.cancel_requested:
            raise JobCancelled("使用者要求取消背景工作。")
        job.progress_current = safe_current
        job.progress_total = safe_total
        job.progress_message = str(message or "背景工作處理中")[:1000]
        job.updated_at = _utc_now()
        session.commit()


def background_job_cancel_requested(job_id: str) -> bool:
    with get_database_session() as session:
        job = session.get(BackgroundJob, str(job_id))
        return bool(job and job.cancel_requested)


def request_background_job_cancel(job_id: str) -> bool:
    with get_database_session() as session:
        job = session.get(BackgroundJob, str(job_id))
        if job is None or job.status in TERMINAL_STATUSES:
            return False
        job.cancel_requested = True
        job.progress_message = "已要求取消，等待目前步驟結束"
        job.updated_at = _utc_now()
        session.commit()
        return True


def mark_background_job_failed(job_id: str, error: Exception | str) -> None:
    now = _utc_now()
    with get_database_session() as session:
        job = session.get(BackgroundJob, str(job_id))
        if job is None:
            return
        job.status = "failed"
        job.error_message = str(error)[:10000]
        job.progress_message = "背景工作執行失敗"
        job.finished_at = now
        job.updated_at = now
        session.commit()


def mark_background_job_cancelled(job_id: str) -> None:
    now = _utc_now()
    with get_database_session() as session:
        job = session.get(BackgroundJob, str(job_id))
        if job is None:
            return
        job.status = "cancelled"
        job.progress_message = "背景工作已取消"
        job.finished_at = now
        job.updated_at = now
        session.commit()


def delete_background_job(job_id: str) -> bool:
    with get_database_session() as session:
        job = session.get(BackgroundJob, str(job_id))
        if job is None or job.status not in TERMINAL_STATUSES:
            return False
        session.delete(job)
        session.commit()
    shutil.rmtree(_job_dir(str(job_id)), ignore_errors=True)
    return True
