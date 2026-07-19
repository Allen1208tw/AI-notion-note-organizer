from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.services import update_service as service


class _DownloadResponse:
    def __init__(self, content: bytes) -> None:
        self.content = content

    def raise_for_status(self) -> None:
        return None

    def iter_content(self, chunk_size: int):
        del chunk_size
        yield self.content


class UpdateServiceTests(unittest.TestCase):
    def test_version_comparison(self) -> None:
        self.assertTrue(service.is_newer_version("3.1.0", "3.0.9"))
        self.assertFalse(service.is_newer_version("3.0", "3.0.0"))

    def test_github_release_requires_expected_asset_and_digest(self) -> None:
        payload = {
            "tag_name": "v3.1.0",
            "draft": False,
            "prerelease": False,
            "body": "release notes",
            "published_at": "2026-07-19T00:00:00Z",
            "html_url": "https://github.com/Allen1208tw/AI-notion-note-organizer/releases/tag/v3.1.0",
            "assets": [
                {
                    "name": service.INSTALLER_ASSET_NAME,
                    "browser_download_url": (
                        "https://github.com/Allen1208tw/AI-notion-note-organizer/"
                        "releases/download/v3.1.0/AI_Notion_Note_Organizer_Setup.exe"
                    ),
                    "digest": f"sha256:{'a' * 64}",
                }
            ],
        }
        info = service.parse_github_release(payload)
        self.assertEqual(info.version, "3.1.0")

        payload["assets"][0]["digest"] = ""
        with self.assertRaises(ValueError):
            service.parse_github_release(payload)

        payload["assets"][0]["digest"] = f"sha256:{'a' * 64}"
        payload["assets"][0]["browser_download_url"] = (
            "https://github.com/someone/other-project/releases/download/v3.1.0/"
            "AI_Notion_Note_Organizer_Setup.exe"
        )
        with self.assertRaises(ValueError):
            service.parse_github_release(payload)

    def test_download_is_kept_only_after_hash_verification(self) -> None:
        content = b"verified installer bytes"
        info = service.UpdateInfo(
            version="3.1.0",
            installer_url=(
                "https://github.com/Allen1208tw/AI-notion-note-organizer/"
                "releases/download/v3.1.0/AI_Notion_Note_Organizer_Setup.exe"
            ),
            sha256=hashlib.sha256(content).hexdigest(),
        )
        with tempfile.TemporaryDirectory() as temporary_dir:
            update_dir = Path(temporary_dir)
            with patch.object(service, "UPDATE_DIR", update_dir), patch.object(
                service.requests,
                "get",
                return_value=_DownloadResponse(content),
            ):
                downloaded = service.download_update(info)
            self.assertEqual(downloaded.read_bytes(), content)


if __name__ == "__main__":
    unittest.main()
