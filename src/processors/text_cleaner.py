import re

def clean_text(raw_text: str) -> str:
    """Normalize extracted document text for later AI analysis."""


    if not raw_text:
     return ""

    cleaned_text = raw_text.replace("\r\n", "\n")
    cleaned_text = cleaned_text.replace("\r", "\n")

    cleaned_text = re.sub(r"[ \t]+", " ", cleaned_text)
    cleaned_text = re.sub(r"\n{3,}", "\n\n", cleaned_text)

    cleaned_text = re.sub(r"(?<!\n)\n(?!\n)", " ", cleaned_text)

    cleaned_text = re.sub(r"[^\S\n]+", " ",      cleaned_text)
    return cleaned_text.strip()

