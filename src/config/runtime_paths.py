from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


APP_DATA_FOLDER_NAME = "AI Notion Note Organizer"


def is_frozen_application() -> bool:
    return bool(getattr(sys, "frozen", False))


def get_resource_dir() -> Path:
    if is_frozen_application() and hasattr(sys, "_MEIPASS"):
        return Path(getattr(sys, "_MEIPASS")).resolve()
    return Path(__file__).resolve().parents[2]


def get_data_dir() -> Path:
    override = os.getenv("AI_NOTION_DATA_DIR", "").strip()
    if override:
        return Path(override).expanduser().resolve()

    if not is_frozen_application():
        return get_resource_dir()

    local_app_data = os.getenv("LOCALAPPDATA", "").strip()
    base = Path(local_app_data) if local_app_data else Path.home() / "AppData" / "Local"
    return (base / APP_DATA_FOLDER_NAME).resolve()


def get_env_file(resource_dir: Path, data_dir: Path) -> Path:
    override = os.getenv("AI_NOTION_ENV_FILE", "").strip()
    if override:
        return Path(override).expanduser().resolve()

    data_env = data_dir / ".env"
    if data_env.exists():
        return data_env.resolve()

    legacy_candidates = []
    if is_frozen_application():
        legacy_candidates.append(Path(sys.executable).resolve().parent / ".env")
    legacy_candidates.append(resource_dir / ".env")

    for candidate in legacy_candidates:
        if candidate.exists():
            data_env.parent.mkdir(parents=True, exist_ok=True)
            try:
                shutil.copy2(candidate, data_env)
                return data_env.resolve()
            except OSError:
                return candidate.resolve()

    return data_env.resolve()


RESOURCE_DIR = get_resource_dir()
DATA_DIR = get_data_dir()
OUTPUT_DIR = DATA_DIR / "outputs"
ENV_FILE = get_env_file(RESOURCE_DIR, DATA_DIR)
