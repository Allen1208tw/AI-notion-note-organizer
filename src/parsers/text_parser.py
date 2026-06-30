from pathlib import Path

def parse_text_file(uploaded_file) -> dict:
    """Read and return text content from a TXT file."""


    raw_bytes = uploaded_file.getvalue()

    try:
        raw_text = raw_bytes.decode("utf-8")
    except UnicodeDecodeError:
        raw_text = raw_bytes.decode("utf-8-sig", errors="replace")

    return {
    "raw_text": raw_text,
    "metadata": {
        "file_name": uploaded_file.name,
        "file_extension": Path(uploaded_file.name).suffix.lower(),
        "file_size": uploaded_file.size,
        "character_count": len(raw_text),
        "page_count": None,
        "paragraph_count": len(
            [line for line in raw_text.splitlines() if line.strip()]
        ),
    },
}

