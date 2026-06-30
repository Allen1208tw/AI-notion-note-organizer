from io import BytesIO
from pathlib import Path

from docx import Document

def parse_docx_file(uploaded_file) -> dict:
    """Read text content and metadata from a DOCX file."""


    document_bytes = uploaded_file.getvalue()
    document = Document(BytesIO(document_bytes))

    paragraphs = [
    paragraph.text.strip()
    for paragraph in document.paragraphs
    if paragraph.text.strip()
]

    raw_text = "\n\n".join(paragraphs)

    return {
    "raw_text": raw_text,
    "metadata": {
        "file_name": uploaded_file.name,
        "file_extension": Path(uploaded_file.name).suffix.lower(),
        "file_size": uploaded_file.size,
        "character_count": len(raw_text),
        "page_count": None,
        "paragraph_count": len(paragraphs),
    },
}

