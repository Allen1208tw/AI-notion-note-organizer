from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class HeadingMatch:
    """章節標題匹配結果。"""

    title: str
    source: str
    start_index: int
    end_index: int
    chapter_number: str = ""


def normalize_heading_text(text: str) -> str:
    """標準化標題文字。"""

    normalized = text.strip()
    normalized = re.sub(r"\s+", " ", normalized)
    normalized = normalized.replace("（", "(").replace("）", ")")
    normalized = normalized.replace("＆", "&")

    return normalized


def normalize_for_compare(text: str) -> str:
    """建立標題比對用文字。"""

    normalized = normalize_heading_text(text)
    normalized = normalized.lower()
    normalized = re.sub(r"\s+", "", normalized)

    return normalized


def clean_heading_title(title: str) -> str:
    """清理章節標題。"""

    cleaned = normalize_heading_text(title)

    cleaned = re.sub(
        r"^\s*(module|chapter|unit)\s*[\d一二三四五六七八九十]+"
        r"[\s：:.\-、]*",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )

    cleaned = re.sub(
        r"^\s*第\s*[\d一二三四五六七八九十]+\s*[章節]\s*"
        r"[\s：:.\-、]*",
        "",
        cleaned,
    )

    cleaned = re.sub(
        r"^\s*\d+\s*[.、]\s*",
        "",
        cleaned,
    )

    return cleaned.strip()


def is_noise_line(line: str) -> bool:
    """判斷是否為頁碼、空白或雜訊。"""

    text = line.strip()

    if not text:
        return True

    if re.fullmatch(r"\d+", text):
        return True

    if text.lower() in {
        "目錄",
        "contents",
        "table of contents",
    }:
        return True

    return False


def line_start_positions(text: str) -> list[tuple[str, int, int]]:
    """取得每一行文字與其在全文中的起訖位置。"""

    lines = []
    current_index = 0

    for line in text.splitlines(keepends=True):
        raw_line = line.rstrip("\r\n")
        start_index = current_index
        end_index = current_index + len(line)

        lines.append(
            (
                raw_line,
                start_index,
                end_index,
            )
        )

        current_index = end_index

    return lines


def extract_module_style_headings(text: str) -> list[HeadingMatch]:
    """
    偵測 Module / Chapter / Unit 類型章節。

    適用：
    Module 1 xxx
    Chapter 1 xxx
    Unit 1 xxx
    M o d u l e 1 xxx
    """

    matches: list[HeadingMatch] = []
    line_positions = line_start_positions(text)

    heading_pattern = re.compile(
        r"^\s*"
        r"(?P<prefix>"
        r"module|m\s*o\s*d\s*u\s*l\s*e|"
        r"chapter|c\s*h\s*a\s*p\s*t\s*e\s*r|"
        r"unit|u\s*n\s*i\s*t"
        r")"
        r"\s*"
        r"(?P<number>[\d一二三四五六七八九十]+)"
        r"[\s：:.\-、]*"
        r"(?P<title>.+)?"
        r"\s*$",
        flags=re.IGNORECASE,
    )

    for line, start_index, end_index in line_positions:
        normalized_line = normalize_heading_text(line)

        match = heading_pattern.match(normalized_line)

        if not match:
            continue

        title = match.group("title") or normalized_line
        title = clean_heading_title(title)

        if not title:
            title = normalized_line

        matches.append(
            HeadingMatch(
                title=title,
                source="module_heading",
                start_index=start_index,
                end_index=end_index,
                chapter_number=match.group("number"),
            )
        )

    return deduplicate_heading_matches(matches)


def extract_numbered_chapter_headings(text: str) -> list[HeadingMatch]:
    """
    偵測一般編號章節。

    適用：
    1. 前言(Preface)
    2. MySQL8.0 安裝與設定
    第 1 章 xxx
    """

    matches: list[HeadingMatch] = []
    line_positions = line_start_positions(text)

    numbered_pattern = re.compile(
        r"^\s*(?P<number>\d{1,2})\s*[.、]\s*(?P<title>.+?)\s*$"
    )

    chinese_chapter_pattern = re.compile(
        r"^\s*第\s*(?P<number>[\d一二三四五六七八九十]+)\s*[章節]\s*"
        r"(?P<title>.+?)\s*$"
    )

    for line, start_index, end_index in line_positions:
        normalized_line = normalize_heading_text(line)

        numbered_match = numbered_pattern.match(normalized_line)

        if numbered_match:
            title = clean_heading_title(
                numbered_match.group("title")
            )

            if title and len(title) <= 80:
                matches.append(
                    HeadingMatch(
                        title=title,
                        source="numbered_heading",
                        start_index=start_index,
                        end_index=end_index,
                        chapter_number=numbered_match.group("number"),
                    )
                )

            continue

        chinese_match = chinese_chapter_pattern.match(normalized_line)

        if chinese_match:
            title = clean_heading_title(
                chinese_match.group("title")
            )

            if title and len(title) <= 80:
                matches.append(
                    HeadingMatch(
                        title=title,
                        source="chinese_chapter_heading",
                        start_index=start_index,
                        end_index=end_index,
                        chapter_number=chinese_match.group("number"),
                    )
                )

    return deduplicate_heading_matches(matches)


def extract_toc_titles(text: str) -> list[str]:
    """
    從目錄頁抽出章節標題。

    適用：
    1. 前言(Preface)
    2. MySQL8.0 安裝與設定
       (Installation & Settings)
    3. 基本查詢(Basic Query)
    """

    lines = [
        normalize_heading_text(line)
        for line in text.splitlines()
    ]

    toc_titles: list[str] = []

    numbered_pattern = re.compile(
        r"^\s*(?P<number>\d{1,2})\s*[.、]\s*(?P<title>.+?)\s*$"
    )

    max_scan_lines = min(
        len(lines),
        300,
    )

    index = 0

    while index < max_scan_lines:
        line = lines[index]

        match = numbered_pattern.match(line)

        if not match:
            index += 1
            continue

        title = match.group("title").strip()

        if not title:
            index += 1
            continue

        next_line = ""

        if index + 1 < max_scan_lines:
            next_line = lines[index + 1].strip()

        should_merge_next_line = (
            next_line.startswith("(")
            and next_line.endswith(")")
        )

        if should_merge_next_line:
            title = f"{title} {next_line}"
            index += 1

        cleaned_title = clean_heading_title(title)

        if (
            cleaned_title
            and len(cleaned_title) <= 100
            and cleaned_title not in toc_titles
        ):
            toc_titles.append(cleaned_title)

        index += 1

    return toc_titles


def title_matches_toc_line(
    line: str,
    toc_title: str,
) -> bool:
    """
    判斷某一行是否等於目錄中的章節標題。

    允許：
    MySQL8.0 安裝與設定 (Installation & Settings)
    MySQL8.0安裝與設定(Installation & Settings)
    """

    compare_line = normalize_for_compare(line)
    compare_title = normalize_for_compare(toc_title)

    return compare_line == compare_title


def extract_toc_based_headings(text: str) -> list[HeadingMatch]:
    """
    使用目錄標題反查正文中的章節位置。

    重點：
    這裡會先抓所有出現位置，
    後面再交給 collapse_repeated_running_headers()
    將連續重複的頁首合併成同一章。
    """

    toc_titles = extract_toc_titles(text)

    if not toc_titles:
        return []

    matches: list[HeadingMatch] = []
    line_positions = line_start_positions(text)

    for line, start_index, end_index in line_positions:
        if is_noise_line(line):
            continue

        normalized_line = normalize_heading_text(line)

        if len(normalized_line) > 120:
            continue

        for title in toc_titles:
            if not title_matches_toc_line(normalized_line, title):
                continue

            matches.append(
                HeadingMatch(
                    title=title,
                    source="toc_heading",
                    start_index=start_index,
                    end_index=end_index,
                )
            )

            break

    return deduplicate_heading_matches(matches)


def deduplicate_heading_matches(
    matches: list[HeadingMatch],
) -> list[HeadingMatch]:
    """去除相同位置的重複標題。"""

    if not matches:
        return []

    sorted_matches = sorted(
        matches,
        key=lambda item: item.start_index,
    )

    deduplicated: list[HeadingMatch] = []
    seen_positions: set[int] = set()

    for match in sorted_matches:
        if match.start_index in seen_positions:
            continue

        seen_positions.add(match.start_index)
        deduplicated.append(match)

    return deduplicated


def remove_toc_duplicate_headings(
    matches: list[HeadingMatch],
) -> list[HeadingMatch]:
    """
    移除目錄頁中的標題，只保留正文真正章節位置。

    同一個 title 第一次通常在目錄，
    後面再次出現才是章節封面或正文標題。
    """

    if not matches:
        return []

    title_count: dict[str, int] = {}

    for match in matches:
        key = normalize_for_compare(match.title)
        title_count[key] = title_count.get(key, 0) + 1

    result: list[HeadingMatch] = []
    seen_title_counter: dict[str, int] = {}

    for match in matches:
        key = normalize_for_compare(match.title)

        seen_title_counter[key] = seen_title_counter.get(key, 0) + 1

        if title_count[key] >= 2 and seen_title_counter[key] == 1:
            continue

        result.append(match)

    return result


def collapse_repeated_running_headers(
    matches: list[HeadingMatch],
) -> list[HeadingMatch]:
    """
    合併投影片每頁重複出現的章節頁首。

    例如：
    MySQL8.0安裝與設定
    MySQL8.0安裝與設定
    MySQL8.0安裝與設定
    基本查詢
    基本查詢

    應該變成：
    MySQL8.0安裝與設定
    基本查詢
    """

    if not matches:
        return []

    collapsed: list[HeadingMatch] = []

    for match in sorted(matches, key=lambda item: item.start_index):
        if not collapsed:
            collapsed.append(match)
            continue

        previous = collapsed[-1]

        same_title = (
            normalize_for_compare(previous.title)
            == normalize_for_compare(match.title)
        )

        if same_title:
            continue

        collapsed.append(match)

    return collapsed


def filter_close_duplicate_headings(
    matches: list[HeadingMatch],
    min_distance: int = 80,
) -> list[HeadingMatch]:
    """
    過濾距離太近的重複標題。

    投影片常會有：
    章節封面頁：表格(Tables)
    下一頁頁首：表格(Tables)

    如果距離太近，保留第一個。
    """

    if not matches:
        return []

    filtered: list[HeadingMatch] = []

    for match in matches:
        if not filtered:
            filtered.append(match)
            continue

        previous = filtered[-1]

        same_title = (
            normalize_for_compare(previous.title)
            == normalize_for_compare(match.title)
        )

        too_close = (
            match.start_index - previous.start_index
            < min_distance
        )

        if same_title and too_close:
            continue

        filtered.append(match)

    return filtered


def build_chapters_from_headings(
    text: str,
    headings: list[HeadingMatch],
) -> list[dict]:
    """依章節標題位置建立主章節資料。"""

    chapters: list[dict] = []

    if not headings:
        return chapters

    sorted_headings = sorted(
        headings,
        key=lambda item: item.start_index,
    )

    for index, heading in enumerate(
        sorted_headings,
        start=1,
    ):
        content_start = heading.start_index

        if index < len(sorted_headings):
            content_end = sorted_headings[index].start_index
        else:
            content_end = len(text)

        content = text[content_start:content_end].strip()

        if not content:
            continue

        chapter = {
            "chapter_id": str(index),
            "title": heading.title,
            "source": heading.source,
            "content": content,
            "start_index": content_start,
            "end_index": content_end,
            "subsections": detect_subsections(
                content,
                parent_chapter_id=str(index),
            ),
        }

        chapters.append(chapter)

    return chapters


def detect_subsections(
    chapter_content: str,
    parent_chapter_id: str,
) -> list[dict]:
    """
    偵測子章節。

    這版會避免把每一頁重複出現的主標題當成子章節。
    """

    subsections: list[dict] = []
    line_positions = line_start_positions(chapter_content)

    subsection_matches: list[HeadingMatch] = []

    subsection_patterns = [
        re.compile(
            r"^\s*(?P<number>\d+[-.]\d+)\s*[：:.\-、]?\s*(?P<title>.+?)\s*$"
        ),
        re.compile(
            r"^\s*[●]\s*(?P<title>.+?)\s*$"
        ),
    ]

    for line, start_index, end_index in line_positions:
        normalized_line = normalize_heading_text(line)

        if is_noise_line(normalized_line):
            continue

        if len(normalized_line) > 100:
            continue

        for pattern in subsection_patterns:
            match = pattern.match(normalized_line)

            if not match:
                continue

            title = clean_heading_title(
                match.group("title")
            )

            if not title:
                continue

            if len(title) > 80:
                continue

            subsection_matches.append(
                HeadingMatch(
                    title=title,
                    source="subsection_heading",
                    start_index=start_index,
                    end_index=end_index,
                    chapter_number=match.groupdict().get(
                        "number",
                        "",
                    ),
                )
            )

            break

    subsection_matches = deduplicate_heading_matches(
        subsection_matches
    )

    subsection_matches = collapse_repeated_running_headers(
        subsection_matches
    )

    subsection_matches = filter_close_duplicate_headings(
        subsection_matches,
        min_distance=50,
    )

    if not subsection_matches:
        return []

    for index, heading in enumerate(
        subsection_matches,
        start=1,
    ):
        content_start = heading.start_index

        if index < len(subsection_matches):
            content_end = subsection_matches[index].start_index
        else:
            content_end = len(chapter_content)

        content = chapter_content[content_start:content_end].strip()

        if not content:
            continue

        subsections.append(
            {
                "section_id": f"{parent_chapter_id}-{index}",
                "title": heading.title,
                "source": heading.source,
                "content": content,
                "start_index": content_start,
                "end_index": content_end,
            }
        )

    return subsections


def detect_fallback_single_chapter(text: str) -> list[dict]:
    """無法偵測章節時，建立單一章節。"""

    content = text.strip()

    if not content:
        return []

    return [
        {
            "chapter_id": "1",
            "title": "整份文件",
            "source": "fallback_single_chapter",
            "content": content,
            "start_index": 0,
            "end_index": len(text),
            "subsections": [],
        }
    ]


def detect_chapters(text: str) -> list[dict]:
    """
    偵測文件主章節。

    偵測順序：
    1. Module / Chapter / Unit 格式
    2. 目錄式投影片 PDF
    3. 一般編號章節
    4. fallback 單一章節
    """

    if not text or not text.strip():
        return []

    module_headings = extract_module_style_headings(text)

    if len(module_headings) >= 2:
        module_headings = remove_toc_duplicate_headings(
            module_headings
        )

        module_headings = collapse_repeated_running_headers(
            module_headings
        )

        module_headings = filter_close_duplicate_headings(
            module_headings
        )

        if len(module_headings) >= 2:
            return build_chapters_from_headings(
                text=text,
                headings=module_headings,
            )

    toc_headings = extract_toc_based_headings(text)

    if len(toc_headings) >= 2:
        toc_headings = remove_toc_duplicate_headings(
            toc_headings
        )

        toc_headings = collapse_repeated_running_headers(
            toc_headings
        )

        toc_headings = filter_close_duplicate_headings(
            toc_headings
        )

        if len(toc_headings) >= 2:
            return build_chapters_from_headings(
                text=text,
                headings=toc_headings,
            )

    numbered_headings = extract_numbered_chapter_headings(text)

    if len(numbered_headings) >= 2:
        numbered_headings = remove_toc_duplicate_headings(
            numbered_headings
        )

        numbered_headings = collapse_repeated_running_headers(
            numbered_headings
        )

        numbered_headings = filter_close_duplicate_headings(
            numbered_headings
        )

        if len(numbered_headings) >= 2:
            return build_chapters_from_headings(
                text=text,
                headings=numbered_headings,
            )

    return detect_fallback_single_chapter(text)