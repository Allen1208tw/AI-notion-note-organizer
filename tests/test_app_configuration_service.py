from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.services import app_configuration_service as service


class AppConfigurationServiceTests(unittest.TestCase):
    def test_notion_url_is_normalized_to_page_id(self) -> None:
        page_id = service.normalize_notion_page_id(
            "https://www.notion.so/My-Page-39c8121fef8e81e1a303e7155b50d954?pvs=4"
        )
        self.assertEqual(page_id, "39c8121fef8e81e1a303e7155b50d954")

    def test_save_preserves_blank_secret_and_validates_chunks(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            env_file = Path(temporary_dir) / ".env"
            env_file.write_text("OPENAI_API_KEY='existing-key'\n", encoding="utf-8")
            with patch.object(service, "ENV_FILE", env_file):
                status = service.save_configuration(
                    openai_api_key="",
                    gemini_api_key="",
                    notion_api_key="new-notion-key",
                    notion_parent_page=(
                        "https://www.notion.so/Page-"
                        "39c8121fef8e81e1a303e7155b50d954"
                    ),
                    ai_provider="openai",
                    openai_chunk_model="gpt-5-mini",
                    openai_merge_model="gpt-5",
                    gemini_detail_model="gemini-3.5-flash",
                    max_file_size_mb=25,
                    chunk_size=6000,
                    chunk_overlap=500,
                    auto_download_updates=False,
                )
                self.assertTrue(status["openai_configured"])
                self.assertTrue(status["notion_api_configured"])

                with self.assertRaises(ValueError):
                    service.save_configuration(
                        openai_api_key="",
                        gemini_api_key="",
                        notion_api_key="",
                        notion_parent_page="",
                        ai_provider="openai",
                        openai_chunk_model="gpt-5-mini",
                        openai_merge_model="gpt-5",
                        gemini_detail_model="gemini-3.5-flash",
                        max_file_size_mb=25,
                        chunk_size=1000,
                        chunk_overlap=1000,
                        auto_download_updates=False,
                    )

    def test_gemini_can_be_selected_without_openai_key(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            env_file = Path(temporary_dir) / ".env"
            env_file.write_text("", encoding="utf-8")
            with patch.object(service, "ENV_FILE", env_file):
                status = service.save_configuration(
                    openai_api_key="",
                    gemini_api_key="gemini-key",
                    notion_api_key="",
                    notion_parent_page="",
                    ai_provider="gemini",
                    openai_chunk_model="gpt-5-mini",
                    openai_merge_model="gpt-5",
                    gemini_detail_model="gemini-3.5-flash",
                    max_file_size_mb=25,
                    chunk_size=6000,
                    chunk_overlap=500,
                    auto_download_updates=False,
                )

                self.assertEqual(status["ai_provider"], "gemini")
                self.assertFalse(status["openai_configured"])
                self.assertTrue(status["gemini_configured"])
                self.assertTrue(status["selected_ai_configured"])


if __name__ == "__main__":
    unittest.main()
