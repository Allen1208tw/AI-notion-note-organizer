from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

import requests

from src.config.settings import APP_AUTO_DOWNLOAD_UPDATES, OUTPUT_DIR
from src.version import __version__


GITHUB_REPOSITORY = "Allen1208tw/AI-notion-note-organizer"
GITHUB_API_URL = (
    f"https://api.github.com/repos/{GITHUB_REPOSITORY}/releases/latest"
)
INSTALLER_ASSET_NAME = "AI_Notion_Note_Organizer_Setup.exe"
ONE_CLICK_DOWNLOAD_URL = (
    f"https://github.com/{GITHUB_REPOSITORY}/releases/latest/download/"
    f"{INSTALLER_ASSET_NAME}"
)
UPDATE_DIR = OUTPUT_DIR / "updates"
UPDATE_STATUS_FILE = UPDATE_DIR / "update_status.json"
VERSION_PATTERN = re.compile(r"^\d+(?:\.\d+){0,3}(?:[-+][0-9A-Za-z.-]+)?$")


@dataclass(frozen=True)
class UpdateInfo:
    version: str
    installer_url: str
    sha256: str
    release_notes: str = ""
    published_at: str = ""
    release_url: str = ""


def _utc_now_text() -> str:
    return datetime.now(UTC).isoformat()


def _version_key(value: str) -> tuple[int, int, int, int]:
    core = str(value).strip().split("-", 1)[0].split("+", 1)[0]
    parts = core.split(".")
    if not parts or any(not part.isdigit() for part in parts):
        raise ValueError(f"版本格式不合法：{value}")
    numbers = [int(part) for part in parts[:4]]
    return tuple((numbers + [0, 0, 0, 0])[:4])


def is_newer_version(candidate: str, current: str = __version__) -> bool:
    return _version_key(candidate) > _version_key(current)


def _validate_github_installer_url(url: str) -> None:
    expected_prefix = f"https://github.com/{GITHUB_REPOSITORY}/releases/download/"
    if not str(url).startswith(expected_prefix):
        raise ValueError("GitHub Release 安裝檔網址不屬於本專案。")


def parse_github_release(data: dict) -> UpdateInfo:
    if not isinstance(data, dict):
        raise TypeError("GitHub Release 回應必須是 JSON Object。")
    if data.get("draft") or data.get("prerelease"):
        raise ValueError("最新 Release 不是正式版本。")

    version = str(data.get("tag_name") or "").strip().lstrip("vV")
    if not VERSION_PATTERN.fullmatch(version):
        raise ValueError("GitHub Release Tag 不是合法版本號。")

    assets = data.get("assets") or []
    asset = next(
        (
            item
            for item in assets
            if isinstance(item, dict)
            and str(item.get("name") or "") == INSTALLER_ASSET_NAME
        ),
        None,
    )
    if asset is None:
        raise ValueError(f"Release 缺少安裝檔：{INSTALLER_ASSET_NAME}")

    installer_url = str(asset.get("browser_download_url") or "").strip()
    _validate_github_installer_url(installer_url)

    digest = str(asset.get("digest") or "").strip().lower()
    if not digest.startswith("sha256:"):
        raise ValueError("GitHub Release Asset 缺少 SHA-256 digest。")
    sha256 = digest.split(":", 1)[1]
    if not re.fullmatch(r"[0-9a-f]{64}", sha256):
        raise ValueError("GitHub Release Asset 的 SHA-256 digest 不合法。")

    return UpdateInfo(
        version=version,
        installer_url=installer_url,
        sha256=sha256,
        release_notes=str(data.get("body") or "").strip(),
        published_at=str(data.get("published_at") or "").strip(),
        release_url=str(data.get("html_url") or "").strip(),
    )


def _write_status(data: dict) -> None:
    UPDATE_DIR.mkdir(parents=True, exist_ok=True)
    temporary = UPDATE_STATUS_FILE.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary.replace(UPDATE_STATUS_FILE)


def read_cached_update_status() -> dict:
    if not UPDATE_STATUS_FILE.exists():
        return {}
    try:
        value = json.loads(UPDATE_STATUS_FILE.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def check_for_updates() -> dict:
    response = requests.get(
        GITHUB_API_URL,
        headers={
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "AI-Notion-Note-Organizer-Updater",
        },
        timeout=10,
    )
    if response.status_code == 404:
        return {
            "status": "not_published",
            "current_version": __version__,
            "checked_at": _utc_now_text(),
            "message": "GitHub 尚未發布正式版本。",
        }
    response.raise_for_status()
    if len(response.content) > 2 * 1024 * 1024:
        raise ValueError("GitHub Release 回應超過 2 MB，已拒絕處理。")

    info = parse_github_release(response.json())
    available = is_newer_version(info.version)
    return {
        "status": "available" if available else "current",
        "current_version": __version__,
        "checked_at": _utc_now_text(),
        "source": GITHUB_API_URL,
        "one_click_download_url": ONE_CLICK_DOWNLOAD_URL,
        "update": asdict(info),
        "message": "發現新版本。" if available else "目前已是最新版本。",
    }


def _download_target(info: UpdateInfo) -> Path:
    safe_version = re.sub(r"[^0-9A-Za-z._-]+", "_", info.version)
    return UPDATE_DIR / f"AI_Notion_Setup_{safe_version}.exe"


def download_update(info: UpdateInfo) -> Path:
    _validate_github_installer_url(info.installer_url)
    target = _download_target(info)
    temporary = target.with_suffix(".exe.part")
    UPDATE_DIR.mkdir(parents=True, exist_ok=True)

    digest = hashlib.sha256()
    response = requests.get(info.installer_url, stream=True, timeout=(10, 120))
    response.raise_for_status()
    with temporary.open("wb") as output:
        for chunk in response.iter_content(chunk_size=1024 * 1024):
            if not chunk:
                continue
            digest.update(chunk)
            output.write(chunk)

    actual_hash = digest.hexdigest().lower()
    if actual_hash != info.sha256.lower():
        temporary.unlink(missing_ok=True)
        raise ValueError("更新安裝檔 SHA-256 驗證失敗，檔案已刪除。")

    temporary.replace(target)
    return target


def check_and_cache_update() -> dict:
    try:
        status = check_for_updates()
        if status.get("status") == "available" and APP_AUTO_DOWNLOAD_UPDATES:
            info = UpdateInfo(**status["update"])
            installer_path = download_update(info)
            status["downloaded_installer"] = str(installer_path)
        _write_status(status)
        return status
    except Exception as error:
        status = {
            "status": "error",
            "current_version": __version__,
            "checked_at": _utc_now_text(),
            "message": str(error),
        }
        _write_status(status)
        return status


def launch_update_installer(installer_path: str | Path) -> None:
    if os.name != "nt":
        raise RuntimeError("自動安裝目前只支援 Windows。")
    path = Path(installer_path).resolve()
    if not path.is_file() or path.suffix.lower() != ".exe":
        raise FileNotFoundError("找不到已驗證的更新安裝檔。")
    subprocess.Popen(
        [
            str(path),
            "/SILENT",
            "/CLOSEAPPLICATIONS",
            "/RESTARTAPPLICATIONS",
        ],
        cwd=path.parent,
    )
