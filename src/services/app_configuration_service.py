from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from dotenv import dotenv_values, set_key

from src.config.runtime_paths import ENV_FILE, OUTPUT_DIR


DEFAULTS = {
    "AI_PROVIDER": "openai",
    "OPENAI_CHUNK_MODEL": "gpt-5-mini",
    "OPENAI_MERGE_MODEL": "gpt-5",
    "GEMINI_DETAIL_MODEL": "gemini-3.5-flash",
    "MAX_FILE_SIZE_MB": "25",
    "CHUNK_SIZE": "6000",
    "CHUNK_OVERLAP": "500",
    "APP_AUTO_DOWNLOAD_UPDATES": "false",
}
SECRET_KEYS = {"OPENAI_API_KEY", "GEMINI_API_KEY", "NOTION_API_KEY"}
RESTART_REQUEST_FILE = OUTPUT_DIR / ".restart_requested"
LEGACY_GEMINI_DEFAULT_MODEL = "gemini-2.5-flash"


def _normalize_gemini_model(value: str) -> str:
    model = str(value or "").strip()
    if not model or model == LEGACY_GEMINI_DEFAULT_MODEL:
        return DEFAULTS["GEMINI_DETAIL_MODEL"]
    return model


def _read_values() -> dict[str, str]:
    if not ENV_FILE.exists():
        return {}
    return {
        str(key): str(value or "")
        for key, value in dotenv_values(ENV_FILE).items()
    }


def _positive_int(value: Any, label: str) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{label} 必須是整數。") from error
    if result <= 0:
        raise ValueError(f"{label} 必須大於 0。")
    return result


def _stored_int(values: dict[str, str], key: str) -> int:
    try:
        return int(values.get(key, DEFAULTS[key]))
    except (TypeError, ValueError):
        return int(DEFAULTS[key])


def normalize_notion_page_id(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    source = text.split("?", 1)[0]
    compact_matches = re.findall(
        r"(?<![0-9a-fA-F])([0-9a-fA-F]{32})(?![0-9a-fA-F])",
        source,
    )
    if compact_matches:
        return compact_matches[-1].lower()

    uuid_matches = re.findall(
        r"(?<![0-9a-fA-F])"
        r"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
        r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12})"
        r"(?![0-9a-fA-F])",
        source,
    )
    if uuid_matches:
        return uuid_matches[-1].replace("-", "").lower()

    raise ValueError("Notion 父頁格式不正確，請貼上頁面網址或 32 位 Page ID。")


def get_configuration_status() -> dict[str, Any]:
    values = _read_values()
    ai_provider = str(
        values.get("AI_PROVIDER", DEFAULTS["AI_PROVIDER"])
    ).strip().lower()
    if ai_provider not in {"openai", "gemini"}:
        ai_provider = DEFAULTS["AI_PROVIDER"]

    return {
        "env_file": str(ENV_FILE),
        "ai_provider": ai_provider,
        "openai_configured": bool(values.get("OPENAI_API_KEY")),
        "gemini_configured": bool(values.get("GEMINI_API_KEY")),
        "notion_api_configured": bool(values.get("NOTION_API_KEY")),
        "notion_parent_configured": bool(values.get("NOTION_PARENT_PAGE_ID")),
        "notion_parent_page_id": values.get("NOTION_PARENT_PAGE_ID", ""),
        "openai_chunk_model": values.get(
            "OPENAI_CHUNK_MODEL",
            DEFAULTS["OPENAI_CHUNK_MODEL"],
        ),
        "openai_merge_model": values.get(
            "OPENAI_MERGE_MODEL",
            DEFAULTS["OPENAI_MERGE_MODEL"],
        ),
        "gemini_detail_model": _normalize_gemini_model(
            values.get("GEMINI_DETAIL_MODEL", DEFAULTS["GEMINI_DETAIL_MODEL"])
        ),
        "selected_ai_configured": (
            bool(values.get("GEMINI_API_KEY"))
            if ai_provider == "gemini"
            else bool(values.get("OPENAI_API_KEY"))
        ),
        "max_file_size_mb": _stored_int(values, "MAX_FILE_SIZE_MB"),
        "chunk_size": _stored_int(values, "CHUNK_SIZE"),
        "chunk_overlap": _stored_int(values, "CHUNK_OVERLAP"),
        "auto_download_updates": values.get(
            "APP_AUTO_DOWNLOAD_UPDATES",
            DEFAULTS["APP_AUTO_DOWNLOAD_UPDATES"],
        ).lower()
        in {"1", "true", "yes", "on"},
    }


def save_configuration(
    *,
    openai_api_key: str,
    gemini_api_key: str,
    notion_api_key: str,
    notion_parent_page: str,
    ai_provider: str,
    openai_chunk_model: str,
    openai_merge_model: str,
    gemini_detail_model: str,
    max_file_size_mb: int,
    chunk_size: int,
    chunk_overlap: int,
    auto_download_updates: bool,
    clear_openai_key: bool = False,
    clear_gemini_key: bool = False,
    clear_notion_key: bool = False,
) -> dict[str, Any]:
    chunk_size_value = _positive_int(chunk_size, "Chunk 大小")
    overlap_value = _positive_int(chunk_overlap, "Chunk 重疊字數")
    max_file_size_value = _positive_int(max_file_size_mb, "最大檔案大小")
    if overlap_value >= chunk_size_value:
        raise ValueError("Chunk 重疊字數必須小於 Chunk 大小。")

    chunk_model = str(openai_chunk_model or "").strip()
    merge_model = str(openai_merge_model or "").strip()
    gemini_model = _normalize_gemini_model(str(gemini_detail_model or "").strip())
    provider = str(ai_provider or DEFAULTS["AI_PROVIDER"]).strip().lower()
    if provider not in {"openai", "gemini"}:
        raise ValueError("AI 供應商只能選擇 OpenAI 或 Gemini。")
    if not chunk_model or not merge_model or not gemini_model:
        raise ValueError("OpenAI 分析模型與合併模型不可空白。")

    current = _read_values()
    updates = {
        "AI_PROVIDER": provider,
        "OPENAI_CHUNK_MODEL": chunk_model,
        "OPENAI_MERGE_MODEL": merge_model,
        "GEMINI_DETAIL_MODEL": gemini_model,
        "MAX_FILE_SIZE_MB": str(max_file_size_value),
        "CHUNK_SIZE": str(chunk_size_value),
        "CHUNK_OVERLAP": str(overlap_value),
        "APP_AUTO_DOWNLOAD_UPDATES": (
            "true" if auto_download_updates else "false"
        ),
    }

    if clear_openai_key:
        updates["OPENAI_API_KEY"] = ""
    elif str(openai_api_key or "").strip():
        updates["OPENAI_API_KEY"] = str(openai_api_key).strip()

    if clear_gemini_key:
        updates["GEMINI_API_KEY"] = ""
    elif str(gemini_api_key or "").strip():
        updates["GEMINI_API_KEY"] = str(gemini_api_key).strip()

    if clear_notion_key:
        updates["NOTION_API_KEY"] = ""
    elif str(notion_api_key or "").strip():
        updates["NOTION_API_KEY"] = str(notion_api_key).strip()

    parent_input = str(notion_parent_page or "").strip()
    if parent_input:
        updates["NOTION_PARENT_PAGE_ID"] = normalize_notion_page_id(parent_input)
    elif "NOTION_PARENT_PAGE_ID" not in current:
        updates["NOTION_PARENT_PAGE_ID"] = ""

    ENV_FILE.parent.mkdir(parents=True, exist_ok=True)
    ENV_FILE.touch(exist_ok=True)
    for key, value in updates.items():
        set_key(str(ENV_FILE), key, value, quote_mode="always")
        os.environ[key] = value

    return get_configuration_status()


def request_application_restart() -> Path:
    RESTART_REQUEST_FILE.parent.mkdir(parents=True, exist_ok=True)
    RESTART_REQUEST_FILE.write_text("restart", encoding="utf-8")
    return RESTART_REQUEST_FILE
