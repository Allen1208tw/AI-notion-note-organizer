from __future__ import annotations

import unittest
from unittest.mock import patch

from src.services import chapter_notion_service, notion_service


class NotionCredentialTests(unittest.TestCase):
    def test_chapter_export_rejects_non_ascii_token_with_actionable_error(self) -> None:
        with patch.object(
            chapter_notion_service,
            "NOTION_API_KEY",
            "你的 Notion Integration Token",
        ):
            with self.assertRaisesRegex(ValueError, "Notion Token"):
                chapter_notion_service._get_notion_client()

    def test_standard_export_rejects_non_ascii_token_with_actionable_error(self) -> None:
        with patch.object(
            notion_service,
            "NOTION_API_KEY",
            "你的 Notion Integration Token",
        ):
            with patch.object(
                notion_service,
                "NOTION_PARENT_PAGE_ID",
                "39c8121fef8e81e1a303e7155b50d954",
            ):
                with self.assertRaisesRegex(ValueError, "Notion Token"):
                    notion_service.get_notion_client()

    def test_chapter_export_rejects_invalid_parent_page_before_api_call(self) -> None:
        with patch.object(
            chapter_notion_service,
            "NOTION_PARENT_PAGE_ID",
            "你的 Notion 父頁",
        ):
            with self.assertRaisesRegex(ValueError, "Notion 父頁"):
                try:
                    chapter_notion_service._create_parent_page(
                        notion=object(),
                        document_name="Python 基礎.pdf",
                    )
                except AttributeError as error:
                    self.fail(f"Notion API call was reached: {error}")

    def test_standard_export_rejects_invalid_parent_page_before_api_call(self) -> None:
        with patch.object(
            notion_service,
            "NOTION_API_KEY",
            "secret_test-token",
        ):
            with patch.object(
                notion_service,
                "NOTION_PARENT_PAGE_ID",
                "你的 Notion 父頁",
            ):
                with self.assertRaisesRegex(ValueError, "Notion 父頁"):
                    notion_service.get_notion_client()


if __name__ == "__main__":
    unittest.main()
