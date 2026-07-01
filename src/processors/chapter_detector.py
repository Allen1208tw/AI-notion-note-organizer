import re


MAIN_CHAPTER_PATTERN = re.compile(
    r"""
    ^
    \s*
    (?P<prefix>
        m\s*o\s*d\s*u\s*l\s*e |
        chapter |
        unit
    )
    \s*
    (?P<number>\d{1,3})
    \s*[\.\-:：]?\s*
    (?P<title>.*?)
    \s*
    $
    """,
    flags=re.IGNORECASE | re.VERBOSE,
)

CHINESE_CHAPTER_PATTERN = re.compile(
    r"""
    ^
    \s*
    第
    \s*
    (?P<number>[0-9一二三四五六七八九十百]+)
    \s*
    章
    \s*[\.\-:：]?\s*
    (?P<title>.*?)
    \s*
    $
    """,
    flags=re.VERBOSE,
)

NUMBERED_SECTION_PATTERN = re.compile(
    r"""
    ^
    \s*
    (?P<number>\d{1,3}(?:[-.]\d{1,3})+)
    \s*[\.\-:：、]?\s*
    (?P<title>.{2,120})
    \s*
    $
    """,
    flags=re.VERBOSE,
)

MARKDOWN_HEADING_PATTERN = re.compile(
    r"^(?P<hashes>#{1,6})\s+(?P<title>.+?)\s*$"
)


def _clean_title(title: str) -> str:
    """清理標題中的多餘空白、頁碼與符號。"""

    cleaned_title = re.sub(r"\s+", " ", title)
    cleaned_title = cleaned_title.strip()

    cleaned_title = re.sub(
        r"\s+\d{1,3}$",
        "",
        cleaned_title,
    )

    return cleaned_title.strip(" .:：-—_")


def _normalize_prefix(prefix: str) -> str:
    """把 M o d u l e 正規化成 Module。"""

    normalized_prefix = re.sub(r"\s+", "", prefix).lower()

    prefix_map = {
        "module": "Module",
        "chapter": "Chapter",
        "unit": "Unit",
    }

    return prefix_map.get(normalized_prefix, prefix.capitalize())


def _is_valid_title(title: str) -> bool:
    """避免程式碼、網址、頁碼、項目符號被當成標題。"""

    cleaned_title = _clean_title(title)

    if len(cleaned_title) < 2 or len(cleaned_title) > 120:
        return False

    if cleaned_title.isdigit():
        return False

    if "http://" in cleaned_title or "https://" in cleaned_title:
        return False

    if cleaned_title.startswith(
        (
            "<",
            "{",
            "}",
            "//",
            "/*",
            "*",
            "⚫",
            "•",
            "-",
        )
    ):
        return False

    if any(symbol in cleaned_title for symbol in ("<", ">", "{", "}")):
        return False

    return True


def _get_lines_with_indexes(text: str) -> list[dict]:
    """保留每一行內容與其原始字元位置。"""

    lines = []
    current_index = 0

    for raw_line in text.splitlines(keepends=True):
        line_text = raw_line.rstrip("\r\n")

        lines.append(
            {
                "text": line_text,
                "start_index": current_index,
                "end_index": current_index + len(line_text),
            }
        )

        current_index += len(raw_line)

    return lines


def _find_next_possible_title(
    lines: list[dict],
    current_line_index: int,
) -> str:
    """
    當 Module 只有寫 Module 1 時，
    從接下來幾行找可能的章節標題。
    """

    for next_index in range(
        current_line_index + 1,
        min(current_line_index + 5, len(lines)),
    ):
        candidate = _clean_title(lines[next_index]["text"])

        if not candidate:
            continue

        if candidate.isdigit():
            continue

        if candidate.startswith(
            (
                "⚫",
                "•",
                "-",
                "<",
                "{",
                "}",
            )
        ):
            continue

        if len(candidate) > 80:
            continue

        if _is_valid_title(candidate):
            return candidate

    return ""


def _detect_main_chapters(text: str) -> list[dict]:
    """只抓真正的大章節，例如 Module、Chapter、Unit、第 X 章。"""

    main_chapters = []
    lines = _get_lines_with_indexes(text)

    for line_index, line_data in enumerate(lines):
        raw_line = line_data["text"]
        stripped_line = raw_line.strip()

        if not stripped_line:
            continue

        main_match = MAIN_CHAPTER_PATTERN.match(stripped_line)

        if main_match:
            prefix = _normalize_prefix(main_match.group("prefix"))
            number = main_match.group("number")
            raw_title = _clean_title(main_match.group("title"))

            if not raw_title:
                raw_title = _find_next_possible_title(
                    lines,
                    line_index,
                )

            title = f"{prefix} {number}"

            if raw_title:
                title = f"{title}｜{raw_title}"

            main_chapters.append(
                {
                    "title": title,
                    "number": number,
                    "source": "main_chapter",
                    "start_index": line_data["start_index"],
                    "end_index": line_data["end_index"],
                }
            )

            continue

        chinese_match = CHINESE_CHAPTER_PATTERN.match(stripped_line)

        if chinese_match:
            number = chinese_match.group("number")
            raw_title = _clean_title(chinese_match.group("title"))

            if not raw_title:
                raw_title = _find_next_possible_title(
                    lines,
                    line_index,
                )

            title = f"第 {number} 章"

            if raw_title:
                title = f"{title}｜{raw_title}"

            main_chapters.append(
                {
                    "title": title,
                    "number": number,
                    "source": "chinese_chapter",
                    "start_index": line_data["start_index"],
                    "end_index": line_data["end_index"],
                }
            )

    return main_chapters


def _detect_subsections(text: str) -> list[dict]:
    """抓 1-1、2-3、17-1 這類子章節。"""

    subsections = []
    lines = _get_lines_with_indexes(text)

    for line_data in lines:
        stripped_line = line_data["text"].strip()

        if not stripped_line:
            continue

        section_match = NUMBERED_SECTION_PATTERN.match(stripped_line)

        if not section_match:
            continue

        number = section_match.group("number")
        raw_title = _clean_title(section_match.group("title"))

        if not _is_valid_title(raw_title):
            continue

        number_parts = re.split(r"[-.]", number)

        if len(number_parts) < 2:
            continue

        subsections.append(
            {
                "title": f"{number}｜{raw_title}",
                "number": number,
                "parent_number": number_parts[0],
                "level": len(number_parts),
                "source": "numbered_section",
                "start_index": line_data["start_index"],
                "end_index": line_data["end_index"],
            }
        )

    return subsections


def _detect_markdown_chapters(text: str) -> list[dict]:
    """
    當文件沒有 Module / Chapter / 第 X 章時，
    才使用 Markdown 標題做主章節。
    """

    chapters = []
    lines = _get_lines_with_indexes(text)

    for line_data in lines:
        stripped_line = line_data["text"].strip()

        markdown_match = MARKDOWN_HEADING_PATTERN.match(stripped_line)

        if not markdown_match:
            continue

        level = len(markdown_match.group("hashes"))
        title = _clean_title(markdown_match.group("title"))

        if not _is_valid_title(title):
            continue

        chapters.append(
            {
                "title": title,
                "number": None,
                "source": "markdown",
                "level": level,
                "start_index": line_data["start_index"],
                "end_index": line_data["end_index"],
            }
        )

    return chapters


def _remove_duplicate_main_chapters(chapters: list[dict]) -> list[dict]:
    """移除重複出現的主章節。"""

    unique_chapters = []
    seen_numbers = set()

    for chapter in sorted(
        chapters,
        key=lambda item: item["start_index"],
    ):
        chapter_number = chapter["number"]

        if chapter_number and chapter_number in seen_numbers:
            continue

        if chapter_number:
            seen_numbers.add(chapter_number)

        unique_chapters.append(chapter)

    return unique_chapters


def _build_subsections_for_parent(
    parent_number: str,
    chapter_start_index: int,
    chapter_end_index: int,
    all_subsections: list[dict],
    text: str,
) -> list[dict]:
    """把符合主章節編號的子章節收進該主章節。"""

    matched_subsections = []

    for subsection in all_subsections:
        is_inside_parent_range = (
            chapter_start_index
            <= subsection["start_index"]
            < chapter_end_index
        )

        is_same_parent_number = (
            subsection["parent_number"] == str(parent_number)
        )

        if not is_inside_parent_range:
            continue

        if not is_same_parent_number:
            continue

        matched_subsections.append(subsection)

    matched_subsections.sort(
        key=lambda item: item["start_index"]
    )

    formatted_subsections = []

    for index, subsection in enumerate(matched_subsections):
        subsection_start_index = subsection["start_index"]

        if index + 1 < len(matched_subsections):
            subsection_end_index = matched_subsections[
                index + 1
            ]["start_index"]
        else:
            subsection_end_index = chapter_end_index

        subsection_content = text[
            subsection_start_index:subsection_end_index
        ].strip()

        formatted_subsections.append(
            {
                "section_id": index + 1,
                "title": subsection["title"],
                "number": subsection["number"],
                "level": subsection["level"],
                "content": subsection_content,
                "start_index": subsection_start_index,
                "end_index": subsection_end_index,
                "source": subsection["source"],
            }
        )

    return formatted_subsections


def detect_chapters(text: str) -> list[dict]:
    """
    偵測文件主章節與其子章節。

    主章節：
    - Module 1
    - M o d u l e 1
    - Chapter 1
    - Unit 1
    - 第 1 章

    子章節：
    - 1-1
    - 2.3
    - 17-1

    回傳時只會把 Module / Chapter 當作 chapters。
    子章節會放在該 chapter 的 subsections 欄位。
    """

    if not text or not text.strip():
        return []

    main_chapters = _detect_main_chapters(text)
    main_chapters = _remove_duplicate_main_chapters(main_chapters)

    if not main_chapters:
        markdown_chapters = _detect_markdown_chapters(text)

        if markdown_chapters:
            main_chapters = markdown_chapters

    if not main_chapters:
        return [
            {
                "chapter_id": 1,
                "title": "文件內容",
                "number": None,
                "level": 1,
                "content": text.strip(),
                "start_index": 0,
                "end_index": len(text),
                "source": "fallback",
                "subsections": [],
            }
        ]

    all_subsections = _detect_subsections(text)
    chapters = []

    for index, main_chapter in enumerate(main_chapters):
        chapter_start_index = main_chapter["start_index"]

        if index + 1 < len(main_chapters):
            chapter_end_index = main_chapters[
                index + 1
            ]["start_index"]
        else:
            chapter_end_index = len(text)

        chapter_content = text[
            chapter_start_index:chapter_end_index
        ].strip()

        parent_number = main_chapter.get("number")

        if parent_number:
            subsections = _build_subsections_for_parent(
                parent_number=str(parent_number),
                chapter_start_index=chapter_start_index,
                chapter_end_index=chapter_end_index,
                all_subsections=all_subsections,
                text=text,
            )
        else:
            subsections = []

        chapters.append(
            {
                "chapter_id": len(chapters) + 1,
                "title": main_chapter["title"],
                "number": parent_number,
                "level": 1,
                "content": chapter_content,
                "start_index": chapter_start_index,
                "end_index": chapter_end_index,
                "source": main_chapter["source"],
                "subsections": subsections,
            }
        )

    return chapters