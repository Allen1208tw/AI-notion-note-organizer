import fitz
from pathlib import Path


def parse_pdf_file(uploaded_file) -> dict:
    """Read text content and metadata from a PDF file."""

    pdf_bytes = uploaded_file.getvalue()
    document = fitz.open(stream=pdf_bytes, filetype="pdf")

    pages_text = []

    for page in document:
        page_text = page.get_text("text").strip()

        if page_text:
            pages_text.append(page_text)

    raw_text = "\n\n".join(pages_text)

    return {
        "raw_text": raw_text,
        "metadata": {
            "file_name": uploaded_file.name,
            "file_extension": Path(uploaded_file.name).suffix.lower(),
            "file_size": uploaded_file.size,
            "character_count": len(raw_text),
            "page_count": len(document),
            "paragraph_count": len(
                [line for line in raw_text.splitlines() if line.strip()]
            ),
        },
    }