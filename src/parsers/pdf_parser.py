from pathlib import Path

import fitz


def parse_pdf_file(uploaded_file) -> dict:
    """
    解析 PDF 文字內容。

    除了 raw_text，也保留每一頁的文字與字元範圍，
    供後續章節定位與圖片視覺分析使用。
    """

    if uploaded_file is None:
        raise ValueError("沒有提供 PDF 檔案。")

    pdf_bytes = uploaded_file.getvalue()

    if not pdf_bytes:
        raise ValueError("PDF 檔案內容為空。")

    document = fitz.open(
        stream=pdf_bytes,
        filetype="pdf",
    )

    try:
        raw_text_parts = []
        page_texts = []
        current_index = 0

        for page_index, page in enumerate(document):
            page_number = page_index + 1
            page_text = page.get_text("text").strip()

            if page_text:
                start_index = current_index
                end_index = start_index + len(page_text)

                page_texts.append(
                    {
                        "page_number": page_number,
                        "text": page_text,
                        "start_index": start_index,
                        "end_index": end_index,
                    }
                )

                raw_text_parts.append(page_text)
                current_index = end_index + 2

        raw_text = "\n\n".join(raw_text_parts).strip()

        if not raw_text:
            raise ValueError(
                "PDF 沒有可擷取的文字內容，可能是掃描型 PDF。"
            )

        file_name = uploaded_file.name
        file_extension = Path(file_name).suffix.lower()

        return {
            "raw_text": raw_text,
            "pdf_bytes": pdf_bytes,
            "page_texts": page_texts,
            "metadata": {
                "file_name": file_name,
                "file_extension": file_extension,
                "page_count": len(document),
                "character_count": len(raw_text),
                "paragraph_count": len(
                    [
                        paragraph
                        for paragraph in raw_text.split("\n\n")
                        if paragraph.strip()
                    ]
                ),
            },
        }

    finally:
        document.close()