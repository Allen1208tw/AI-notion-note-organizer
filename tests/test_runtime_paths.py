from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.config import runtime_paths


class RuntimePathTests(unittest.TestCase):
    def test_env_file_overrides_stale_inherited_application_setting(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            env_file = Path(temp_dir) / ".env"
            env_file.write_text(
                "NOTION_PARENT_PAGE_ID='38f8121fef8e80a7be3ef6aa24ee750b'\n",
                encoding="utf-8",
            )
            child_environment = os.environ.copy()
            child_environment["AI_NOTION_ENV_FILE"] = str(env_file)
            child_environment["NOTION_PARENT_PAGE_ID"] = "stale-parent-page"

            result = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    (
                        "from src.config.settings import NOTION_PARENT_PAGE_ID; "
                        "print(NOTION_PARENT_PAGE_ID)"
                    ),
                ],
                cwd=Path(__file__).resolve().parents[1],
                env=child_environment,
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=True,
            )

        self.assertEqual(
            result.stdout.strip(),
            "38f8121fef8e80a7be3ef6aa24ee750b",
        )

    def test_frozen_env_file_is_migrated_from_install_dir_to_data_dir(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            install_dir = root / "install"
            data_dir = root / "data"
            install_dir.mkdir()
            data_dir.mkdir()

            legacy_env = install_dir / ".env"
            legacy_env.write_text(
                "OPENAI_API_KEY='old-key'\nNOTION_API_KEY='old-notion'\n",
                encoding="utf-8",
            )

            fake_exe = install_dir / "AI_Notion_Note_Organizer.exe"
            fake_exe.write_text("", encoding="utf-8")

            with patch.object(runtime_paths.sys, "frozen", True, create=True):
                with patch.object(runtime_paths.sys, "executable", str(fake_exe)):
                    env_file = runtime_paths.get_env_file(
                        resource_dir=install_dir / "_internal",
                        data_dir=data_dir,
                    )

            self.assertEqual(env_file, (data_dir / ".env").resolve())
            self.assertTrue((data_dir / ".env").exists())
            self.assertIn(
                "old-key",
                (data_dir / ".env").read_text(encoding="utf-8"),
            )

    def test_existing_data_env_has_priority(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            install_dir = root / "install"
            data_dir = root / "data"
            install_dir.mkdir()
            data_dir.mkdir()

            (install_dir / ".env").write_text(
                "OPENAI_API_KEY='legacy'\n",
                encoding="utf-8",
            )
            (data_dir / ".env").write_text(
                "OPENAI_API_KEY='current'\n",
                encoding="utf-8",
            )

            fake_exe = install_dir / "AI_Notion_Note_Organizer.exe"
            fake_exe.write_text("", encoding="utf-8")

            with patch.object(runtime_paths.sys, "frozen", True, create=True):
                with patch.object(runtime_paths.sys, "executable", str(fake_exe)):
                    env_file = runtime_paths.get_env_file(
                        resource_dir=install_dir / "_internal",
                        data_dir=data_dir,
                    )

            self.assertEqual(env_file, (data_dir / ".env").resolve())
            self.assertIn(
                "current",
                env_file.read_text(encoding="utf-8"),
            )


if __name__ == "__main__":
    unittest.main()
