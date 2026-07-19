from __future__ import annotations

import json
import base64
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from src.services import chapter_cache_service
from src.services.chapter_cache_service import load_chapter_cache
from src.services.chapter_cache_service import save_visual_context_cache
from src.services.chapter_notion_service import (
    _clean_mermaid_code,
    _code_block,
)
from src.validators.mermaid_validator import sanitize_mermaid_for_notion


def _minimal_chapter_note(title: str) -> dict:
    return {
        "chapter_title": title,
        "learning_objectives": ["了解本章重點"],
        "chapter_summary": "本章摘要",
        "plain_explanation": "白話講解",
        "key_points": ["重點"],
        "important_terms": [],
        "syntax_rules": [],
        "code_examples": [],
        "common_mistakes": [],
        "subsections": [],
        "callout_notes": [],
        "comparison_tables": [],
        "image_insights": [],
        "practice_tips": [],
        "mermaid": "flowchart TD\nA --> B",
        "quiz": [],
        "flashcards": [],
    }


class ChapterCacheAndNotionBlockTests(unittest.TestCase):
    def test_single_existing_cache_is_not_reused_for_another_chapter(self) -> None:
        original_cache_dir = chapter_cache_service.CHAPTER_CACHE_DIR

        with tempfile.TemporaryDirectory() as temp_dir:
            chapter_cache_service.CHAPTER_CACHE_DIR = Path(temp_dir)

            try:
                first_chapter = {
                    "chapter_id": "1",
                    "title": "第一章",
                    "content": "第一章內容",
                }
                first_cache_path = (
                    chapter_cache_service._get_chapter_cache_path(
                        "sample.pdf",
                        first_chapter,
                    )
                )
                first_cache_path.parent.mkdir(parents=True, exist_ok=True)
                first_cache_path.write_text(
                    json.dumps(
                        {
                            "cache_version": chapter_cache_service.CACHE_VERSION,
                            "created_at": datetime.utcnow().isoformat(),
                            "updated_at": datetime.utcnow().isoformat(),
                            "visual_analysis_completed": False,
                            "visual_context": [],
                            "chapter_note_completed": True,
                            "chapter_note": _minimal_chapter_note("第一章"),
                        },
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )

                second_chapter_result = load_chapter_cache(
                    "sample.pdf",
                    {
                        "chapter_id": "2",
                        "title": "第二章",
                        "content": "第二章內容",
                    },
                )

                self.assertFalse(second_chapter_result["note_cached"])
                self.assertIsNone(second_chapter_result["chapter_note"])
                self.assertNotEqual(
                    second_chapter_result["cache_path"],
                    first_cache_path,
                )

            finally:
                chapter_cache_service.CHAPTER_CACHE_DIR = original_cache_dir

    def test_mermaid_code_block_uses_notion_mermaid_language(self) -> None:
        cleaned = _clean_mermaid_code(
            "```mermaid\nflowchart TD\nA --> B\n```"
        )
        block = _code_block(cleaned, language="mermaid")

        self.assertEqual(cleaned, "flowchart TD\nA --> B")
        self.assertEqual(block["code"]["language"], "mermaid")
        self.assertNotIn("```", block["code"]["rich_text"][0]["text"]["content"])

    def test_mermaid_labels_escape_html_and_css_special_symbols(self) -> None:
        mermaid = """
flowchart TD
    A[<div class="card">]
    B["CSS selector: #main > .item"]
    C{display: block | inline}
    A --> B
    B --> C
""".strip()

        cleaned = sanitize_mermaid_for_notion(mermaid)

        self.assertIn("＜div class＝", cleaned)
        self.assertIn("＃main ＞ .item", cleaned)
        self.assertIn("display： block ｜ inline", cleaned)
        self.assertIn("A --> B", cleaned)
        self.assertNotIn("<div", cleaned)
        self.assertNotIn("#main >", cleaned)

    def test_visual_cache_keeps_images_as_files_and_restores_data_urls(self) -> None:
        original_cache_dir = chapter_cache_service.CHAPTER_CACHE_DIR

        with tempfile.TemporaryDirectory() as temp_dir:
            chapter_cache_service.CHAPTER_CACHE_DIR = Path(temp_dir)

            try:
                image_bytes = b"fake-png-bytes"
                data_url = (
                    "data:image/png;base64,"
                    + base64.b64encode(image_bytes).decode("utf-8")
                )
                chapter = {
                    "chapter_id": "1",
                    "title": "圖片章節",
                    "content": "內容",
                }

                cache_path = save_visual_context_cache(
                    document_name="visual.pdf",
                    chapter=chapter,
                    visual_context=[
                        {
                            "page_number": 3,
                            "title": "畫面截圖",
                            "description": "測試圖片",
                            "image_data_url": data_url,
                        }
                    ],
                )

                raw_cache = json.loads(cache_path.read_text(encoding="utf-8"))
                cached_item = raw_cache["visual_context"][0]
                self.assertNotIn("image_data_url", cached_item)
                self.assertIn("image_cache_path", cached_item)

                loaded = load_chapter_cache("visual.pdf", chapter)
                loaded_item = loaded["visual_context"][0]
                self.assertTrue(
                    loaded_item["image_data_url"].startswith(
                        "data:image/png;base64,"
                    )
                )
                self.assertEqual(
                    base64.b64decode(
                        loaded_item["image_data_url"].split(",", 1)[1]
                    ),
                    image_bytes,
                )

            finally:
                chapter_cache_service.CHAPTER_CACHE_DIR = original_cache_dir


if __name__ == "__main__":
    unittest.main()
