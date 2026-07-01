import base64

import fitz


def get_pdf_page_count(pdf_bytes: bytes) -> int:
    """取得 PDF 總頁數。"""

    document = fitz.open(
        stream=pdf_bytes,
        filetype="pdf",
    )

    try:
        return len(document)

    finally:
        document.close()


def render_pdf_page_to_base64(
    pdf_bytes: bytes,
    page_number: int,
    zoom: float = 1.5,
) -> str:
    """
    將指定 PDF 頁面轉成 PNG Base64 Data URL。

    page_number 從 1 開始。
    """

    if page_number < 1:
        raise ValueError("page_number 必須從 1 開始。")

    document = fitz.open(
        stream=pdf_bytes,
        filetype="pdf",
    )

    try:
        page_count = len(document)

        if page_number > page_count:
            raise ValueError(
                f"PDF 只有 {page_count} 頁，找不到第 {page_number} 頁。"
            )

        page = document[page_number - 1]

        matrix = fitz.Matrix(
            zoom,
            zoom,
        )

        pixmap = page.get_pixmap(
            matrix=matrix,
            alpha=False,
        )

        image_bytes = pixmap.tobytes("png")

        encoded_image = base64.b64encode(
            image_bytes
        ).decode("utf-8")

        return f"data:image/png;base64,{encoded_image}"

    finally:
        document.close()


def render_pdf_pages_to_base64(
    pdf_bytes: bytes,
    page_numbers: list[int],
    zoom: float = 1.5,
    max_pages: int = 3,
) -> list[dict]:
    """
    將多個 PDF 頁面轉成圖片資料。

    預設最多處理 3 頁，避免一次送太多圖片給 AI。
    """

    if not pdf_bytes:
        raise ValueError("PDF 檔案內容為空。")

    if max_pages < 1:
        raise ValueError("max_pages 至少要是 1。")

    unique_page_numbers = []

    for page_number in page_numbers:
        if page_number not in unique_page_numbers:
            unique_page_numbers.append(page_number)

    selected_page_numbers = unique_page_numbers[:max_pages]

    rendered_pages = []

    for page_number in selected_page_numbers:
        image_data_url = render_pdf_page_to_base64(
            pdf_bytes=pdf_bytes,
            page_number=page_number,
            zoom=zoom,
        )

        rendered_pages.append(
            {
                "page_number": page_number,
                "image_data_url": image_data_url,
            }
        )

    return rendered_pages


def select_representative_pages(
    start_page: int,
    end_page: int,
    max_pages: int = 3,
) -> list[int]:
    """
    從一個章節的頁碼範圍中挑出代表頁。

    優先保留：
    - 章節第一頁
    - 章節中間頁
    - 章節最後頁
    """

    if start_page < 1:
        raise ValueError("start_page 必須從 1 開始。")

    if end_page < start_page:
        raise ValueError("end_page 不可小於 start_page。")

    if max_pages < 1:
        raise ValueError("max_pages 至少要是 1。")

    all_pages = list(
        range(
            start_page,
            end_page + 1,
        )
    )

    if len(all_pages) <= max_pages:
        return all_pages

    if max_pages == 1:
        return [start_page]

    if max_pages == 2:
        return [start_page, end_page]

    middle_page = (start_page + end_page) // 2

    selected_pages = [
        start_page,
        middle_page,
        end_page,
    ]

    return selected_pages[:max_pages]