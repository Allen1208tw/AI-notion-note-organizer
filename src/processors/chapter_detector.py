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

    cleaned = re.sub(
        r"\s*、\s*",
        "、",
        cleaned,
    )

    cleaned = re.sub(
        r"\s*，\s*",
        "，",
        cleaned,
    )

    cleaned = re.sub(
        r"(?<![A-Za-z])"
        r"C\s+S\s+S"
        r"(?![A-Za-z])",
        "CSS",
        cleaned,
        flags=re.IGNORECASE,
    )

    cleaned = re.sub(
        r"(?<![A-Za-z])"
        r"H\s+T\s+M\s+L"
        r"(?![A-Za-z])",
        "HTML",
        cleaned,
        flags=re.IGNORECASE,
    )

    cleaned = re.sub(
        r"\s+",
        " ",
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



def is_generic_chapter_title(
    title: str,
    chapter_number: str = "",
) -> bool:
    """判斷標題是否只有 Module / Chapter 編號，沒有實際主題。"""

    normalized = normalize_heading_text(title)

    if not normalized:
        return True

    patterns = [
        r"^(module|chapter|unit)\s*[\d一二三四五六七八九十]+[：:.\-、]*$",
        r"^第\s*[\d一二三四五六七八九十]+\s*[章節][：:.\-、]*$",
        r"^[\d一二三四五六七八九十]+[：:.\-、]*$",
    ]

    for pattern in patterns:
        if re.fullmatch(
            pattern,
            normalized,
            flags=re.IGNORECASE,
        ):
            return True

    cleaned = clean_heading_title(normalized)

    if not cleaned:
        return True

    if (
        chapter_number
        and normalize_for_compare(cleaned)
        == normalize_for_compare(chapter_number)
    ):
        return True

    return False


def looks_like_title_continuation(
    text: str,
) -> bool:
    """判斷文字是否適合併入跨行章節標題。"""

    normalized = normalize_heading_text(
        text
    )

    if not normalized:
        return False

    if is_noise_line(normalized):
        return False

    if len(normalized) > 80:
        return False

    if re.match(
        r"^\s*(module|chapter|unit)\s*"
        r"[\d一二三四五六七八九十]+",
        normalized,
        flags=re.IGNORECASE,
    ):
        return False

    if re.match(
        r"^\s*第\s*[\d一二三四五六七八九十]+\s*[章節]",
        normalized,
    ):
        return False

    if re.match(
        r"^\s*[•●▪➢✓\-]\s*",
        normalized,
    ):
        return False

    sentence_endings = (
        "。",
        "！",
        "？",
        ".",
        "!",
        "?",
    )

    if normalized.endswith(
        sentence_endings
    ):
        return False

    if any(
        keyword in normalized
        for keyword in (
            "程式碼範例",
            "執行結果",
            "圖:",
            "圖：",
            "說明",
        )
    ):
        return False

    return True


def find_next_meaningful_title_lines(
    line_positions: list[tuple[str, int, int]],
    current_index: int,
    max_lookahead: int = 5,
    max_title_lines: int = 3,
) -> tuple[str, int]:
    """
    往後收集一到多行章節標題。

    適用：
    Module 4.
    字串、列表、元組、
    字典、集合
    """

    collected_lines: list[str] = []
    resolved_end_index = (
        line_positions[current_index][2]
    )

    upper_bound = min(
        len(line_positions),
        current_index + max_lookahead + 1,
    )

    for next_index in range(
        current_index + 1,
        upper_bound,
    ):
        line, _, end_index = line_positions[
            next_index
        ]

        normalized = normalize_heading_text(
            line
        )

        if not normalized:
            if collected_lines:
                break

            continue

        if is_noise_line(normalized):
            if collected_lines:
                break

            continue

        if not looks_like_title_continuation(
            normalized
        ):
            break

        cleaned = clean_heading_title(
            normalized
        )

        if not cleaned:
            continue

        collected_lines.append(
            cleaned
        )

        resolved_end_index = end_index

        if len(collected_lines) >= max_title_lines:
            break

        if not cleaned.endswith(
            (
                "、",
                "，",
                ",",
                "/",
                "／",
                "&",
                "與",
                "及",
            )
        ):
            # 若這一行已像完整標題，仍允許下一行為短標題補充；
            # 但只在下一行非常短且同樣像標題時合併。
            if next_index + 1 < upper_bound:
                next_line = normalize_heading_text(
                    line_positions[
                        next_index + 1
                    ][0]
                )

                if not (
                    1 <= len(next_line) <= 20
                    and looks_like_title_continuation(
                        next_line
                    )
                ):
                    break
            else:
                break

    if not collected_lines:
        return "", line_positions[
            current_index
        ][2]

    combined_title = " ".join(
        collected_lines
    )

    combined_title = re.sub(
        r"\s*([、，,／/&])\s*",
        r"\1",
        combined_title,
    )

    return (
        combined_title.strip(),
        resolved_end_index,
    )


def extract_module_toc_map(
    text: str,
) -> dict[str, str]:
    """
    從文件前段目錄建立 Module 編號與完整標題映射。

    支援：
    Module 1. Python 技術及開發環境介紹

    也支援：
    Module 1.
    Python 技術及開發環境介紹
    """

    line_positions = line_start_positions(
        text
    )

    max_scan_lines = min(
        len(line_positions),
        350,
    )

    heading_pattern = re.compile(
        r"^\s*"
        r"(?P<prefix>"
        r"module|m\s*o\s*d\s*u\s*l\s*e|"
        r"chapter|c\s*h\s*a\s*p\s*t\s*e\s*r|"
        r"unit|u\s*n\s*i\s*t"
        r")"
        r"\s*"
        r"(?P<number>(?:\d\s*){1,3}|[一二三四五六七八九十]+)"
        r"[\s：:.\-、]*"
        r"(?P<title>.*)"
        r"\s*$",
        flags=re.IGNORECASE,
    )

    toc_map: dict[str, str] = {}

    for index in range(max_scan_lines):
        line, _, _ = line_positions[index]

        normalized = normalize_heading_text(
            line
        )

        match = heading_pattern.match(
            normalized
        )

        if not match:
            continue

        chapter_number = re.sub(
            r"\s+",
            "",
            match.group(
                "number"
            )
            or "",
        )

        raw_title = (
            match.group("title")
            or ""
        ).strip()

        title = clean_heading_title(
            raw_title
        )

        if is_generic_chapter_title(
            title,
            chapter_number,
        ):
            title, _ = (
                find_next_meaningful_title_lines(
                    line_positions,
                    index,
                )
            )

        if (
            title
            and not is_generic_chapter_title(
                title,
                chapter_number,
            )
            and len(title) <= 120
        ):
            toc_map.setdefault(
                chapter_number,
                title,
            )

    return toc_map


def make_descriptive_fallback_title(
    chapter_number: str,
    chapter_content_preview: str,
) -> str:
    """
    無法從標題或目錄取得名稱時，
    從章節前幾行推導可理解的 fallback 標題。
    """

    for line in chapter_content_preview.splitlines()[:12]:
        normalized = normalize_heading_text(
            line
        )

        if is_noise_line(normalized):
            continue

        if is_generic_chapter_title(
            normalized,
            chapter_number,
        ):
            continue

        cleaned = clean_heading_title(
            normalized
        )

        if (
            cleaned
            and 2 <= len(cleaned) <= 80
        ):
            return cleaned

    return f"Module {chapter_number}"


def extract_module_style_headings(text: str) -> list[HeadingMatch]:
    """
    偵測 Module / Chapter / Unit 類型章節。

    支援：
    Module 1 Python 技術及開發環境介紹
    Module 1.
    Python 技術及開發環境介紹
    Chapter 1 xxx
    Unit 1 xxx
    M o d u l e 1 xxx

    標題取得優先順序：
    1. 同一行完整標題
    2. 文件目錄中的編號標題映射
    3. 下一個有意義的文字行
    4. 內容預覽推導
    5. 最後才回退為 Module N
    """

    matches: list[HeadingMatch] = []
    line_positions = line_start_positions(text)
    toc_map = extract_module_toc_map(text)

    heading_pattern = re.compile(
        r"^\s*"
        r"(?P<prefix>"
        r"module|m\s*o\s*d\s*u\s*l\s*e|"
        r"chapter|c\s*h\s*a\s*p\s*t\s*e\s*r|"
        r"unit|u\s*n\s*i\s*t"
        r")"
        r"\s*"
        r"(?P<number>(?:\d\s*){1,3}|[一二三四五六七八九十]+)"
        r"[\s：:.\-、]*"
        r"(?P<title>.*)"
        r"\s*$",
        flags=re.IGNORECASE,
    )

    for index, (
        line,
        start_index,
        end_index,
    ) in enumerate(line_positions):
        normalized_line = normalize_heading_text(
            line
        )

        match = heading_pattern.match(
            normalized_line
        )

        if not match:
            continue

        chapter_number = re.sub(
            r"\s+",
            "",
            match.group(
                "number"
            )
            or "",
        )

        raw_title = (
            match.group("title")
            or ""
        ).strip()

        title = clean_heading_title(
            raw_title
        )

        resolved_end_index = end_index

        should_extend_inline_title = bool(
            title
            and title.endswith(
                (
                    "、",
                    "，",
                    ",",
                    "/",
                    "／",
                    "&",
                    "與",
                    "及",
                )
            )
        )

        if should_extend_inline_title:
            (
                continuation_title,
                continuation_end_index,
            ) = find_next_meaningful_title_lines(
                line_positions,
                index,
                max_lookahead=4,
                max_title_lines=2,
            )

            if continuation_title:
                title = (
                    f"{title}{continuation_title}"
                )

                resolved_end_index = (
                    continuation_end_index
                )

        if is_generic_chapter_title(
            title,
            chapter_number,
        ):
            toc_title = toc_map.get(
                chapter_number,
                "",
            )

            if toc_title:
                title = toc_title

        if is_generic_chapter_title(
            title,
            chapter_number,
        ):
            (
                next_line_title,
                next_line_end_index,
            ) = find_next_meaningful_title_lines(
                line_positions,
                index,
            )

            if next_line_title:
                title = next_line_title
                resolved_end_index = (
                    next_line_end_index
                )

        if is_generic_chapter_title(
            title,
            chapter_number,
        ):
            preview_end = min(
                len(text),
                end_index + 600,
            )

            title = (
                make_descriptive_fallback_title(
                    chapter_number=chapter_number,
                    chapter_content_preview=text[
                        end_index:preview_end
                    ],
                )
            )

        title = clean_heading_title(
            title
        )

        if not title:
            title = f"Module {chapter_number}"

        matches.append(
            HeadingMatch(
                title=title,
                source="module_heading",
                start_index=start_index,
                end_index=resolved_end_index,
                chapter_number=chapter_number,
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

        same_chapter_number = (
            str(
                previous.chapter_number
                or ""
            ).strip()
            == str(
                match.chapter_number
                or ""
            ).strip()
        )

        if (
            same_title
            and same_chapter_number
        ):
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

        same_chapter_number = (
            str(
                previous.chapter_number
                or ""
            ).strip()
            == str(
                match.chapter_number
                or ""
            ).strip()
        )

        too_close = (
            match.start_index - previous.start_index
            < min_distance
        )

        if (
            same_title
            and same_chapter_number
            and too_close
        ):
            continue

        filtered.append(match)

    return filtered



def chapter_number_to_int(
    value: str,
) -> int | None:
    """將阿拉伯或簡單中文章節編號轉成整數。"""

    normalized = str(value or "").strip()

    if not normalized:
        return None

    if normalized.isdigit():
        return int(normalized)

    chinese_digit_map = {
        "零": 0,
        "一": 1,
        "二": 2,
        "三": 3,
        "四": 4,
        "五": 5,
        "六": 6,
        "七": 7,
        "八": 8,
        "九": 9,
        "十": 10,
    }

    if normalized in chinese_digit_map:
        return chinese_digit_map[normalized]

    if normalized.startswith("十"):
        tail = normalized[1:]

        if not tail:
            return 10

        tail_value = chinese_digit_map.get(
            tail
        )

        if tail_value is not None:
            return 10 + tail_value

    if "十" in normalized:
        head, tail = normalized.split(
            "十",
            maxsplit=1,
        )

        head_value = chinese_digit_map.get(
            head,
            1,
        )

        tail_value = chinese_digit_map.get(
            tail,
            0,
        )

        return head_value * 10 + tail_value

    return None


def select_primary_module_sequence(
    headings: list[HeadingMatch],
) -> list[HeadingMatch]:
    """
    從目錄、正文與附錄中選出真正的主章節序列。

    核心原則：
    1. 優先尋找從 Module 1 開始的連續序列
    2. 同樣章節數時，選擇涵蓋文字範圍較大的序列
       - 目錄中的 1～10 通常集中在很短的文字範圍
       - 正文章節的 1～10 會橫跨整份教材
    3. 不再單純選擇「局部最長遞增段」
       避免錯把 3～10 選成主教材並遺失 1、2
    4. 找不到從 1 開始的序列時，才使用一般遞增序列 fallback
    """

    if not headings:
        return []

    sorted_headings = sorted(
        headings,
        key=lambda item: item.start_index,
    )

    numbered_headings: list[
        tuple[HeadingMatch, int]
    ] = []

    for heading in sorted_headings:
        number_value = chapter_number_to_int(
            heading.chapter_number
        )

        if number_value is None:
            continue

        numbered_headings.append(
            (
                heading,
                number_value,
            )
        )

    if not numbered_headings:
        return sorted_headings

    chapter_one_indices = [
        index
        for index, (_, number_value)
        in enumerate(numbered_headings)
        if number_value == 1
    ]

    candidates: list[
        list[HeadingMatch]
    ] = []

    for start_index in chapter_one_indices:
        first_heading, _ = numbered_headings[
            start_index
        ]

        candidate = [
            first_heading
        ]

        expected_number = 2
        search_index = start_index + 1
        current_position = (
            first_heading.start_index
        )

        while search_index < len(
            numbered_headings
        ):
            found_heading = None
            found_index = None

            for candidate_index in range(
                search_index,
                len(numbered_headings),
            ):
                (
                    possible_heading,
                    possible_number,
                ) = numbered_headings[
                    candidate_index
                ]

                if (
                    possible_heading.start_index
                    <= current_position
                ):
                    continue

                if possible_number == 1:
                    break

                if (
                    possible_number
                    == expected_number
                ):
                    found_heading = (
                        possible_heading
                    )

                    found_index = (
                        candidate_index
                    )

                    break

                if possible_number > expected_number:
                    break

            if (
                found_heading is None
                or found_index is None
            ):
                break

            candidate.append(
                found_heading
            )

            current_position = (
                found_heading.start_index
            )

            search_index = found_index + 1
            expected_number += 1

        candidates.append(
            candidate
        )

    if candidates:
        def candidate_score(
            candidate: list[HeadingMatch],
        ) -> tuple[int, int, int]:
            chapter_count = len(
                candidate
            )

            text_span = (
                candidate[-1].start_index
                - candidate[0].start_index
                if chapter_count >= 2
                else 0
            )

            later_start_bonus = (
                candidate[0].start_index
            )

            return (
                chapter_count,
                text_span,
                later_start_bonus,
            )

        best_candidate = max(
            candidates,
            key=candidate_score,
        )

        if len(best_candidate) >= 2:
            return best_candidate

    runs: list[
        list[HeadingMatch]
    ] = []

    current_run: list[
        HeadingMatch
    ] = []

    previous_number: int | None = None
    seen_numbers: set[int] = set()

    for heading, number_value in (
        numbered_headings
    ):
        should_split = False

        if previous_number is not None:
            if number_value <= previous_number:
                should_split = True

            if number_value in seen_numbers:
                should_split = True

        if should_split:
            if current_run:
                runs.append(
                    current_run
                )

            current_run = []
            seen_numbers = set()

        current_run.append(
            heading
        )

        seen_numbers.add(
            number_value
        )

        previous_number = (
            number_value
        )

    if current_run:
        runs.append(
            current_run
        )

    if not runs:
        return sorted_headings

    return max(
        runs,
        key=lambda run: (
            len(run),
            (
                run[-1].start_index
                - run[0].start_index
                if len(run) >= 2
                else 0
            ),
        ),
    )


def ensure_unique_chapter_source_ids(
    chapters: list[dict],
) -> list[dict]:
    """
    確保同一份文件內 source chapter id 唯一。

    這是寫入 SQLite 前的最後一道防護。
    正常情況下主章節序列篩選後不會觸發。
    """

    used_ids: set[str] = set()
    normalized_chapters: list[dict] = []

    for index, chapter in enumerate(
        chapters,
        start=1,
    ):
        item = dict(chapter)

        source_id = str(
            item.get("chapter_id")
            or index
        ).strip()

        if (
            not source_id
            or source_id in used_ids
        ):
            source_id = str(index)

            suffix = 2

            while source_id in used_ids:
                source_id = (
                    f"{index}-{suffix}"
                )

                suffix += 1

        used_ids.add(
            source_id
        )

        item["chapter_id"] = source_id

        normalized_chapters.append(
            item
        )

    return normalized_chapters


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

        resolved_chapter_id = (
            str(heading.chapter_number).strip()
            if str(heading.chapter_number).strip()
            else str(index)
        )

        resolved_title = clean_heading_title(
            heading.title
        )

        if is_generic_chapter_title(
            resolved_title,
            resolved_chapter_id,
        ):
            resolved_title = (
                make_descriptive_fallback_title(
                    chapter_number=resolved_chapter_id,
                    chapter_content_preview=content,
                )
            )

        chapter = {
            "chapter_id": resolved_chapter_id,
            "title": resolved_title,
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
        module_headings = deduplicate_heading_matches(
            module_headings
        )

        module_headings = select_primary_module_sequence(
            module_headings
        )

        module_headings = collapse_repeated_running_headers(
            module_headings
        )

        module_headings = filter_close_duplicate_headings(
            module_headings
        )

        if len(module_headings) >= 2:
            chapters = build_chapters_from_headings(
                text=text,
                headings=module_headings,
            )

            return ensure_unique_chapter_source_ids(
                chapters
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
            chapters = build_chapters_from_headings(
                text=text,
                headings=toc_headings,
            )

            return ensure_unique_chapter_source_ids(
                chapters
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
            chapters = build_chapters_from_headings(
                text=text,
                headings=numbered_headings,
            )

            return ensure_unique_chapter_source_ids(
                chapters
            )

    return detect_fallback_single_chapter(text)