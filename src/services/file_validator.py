from pathlib import Path

from src.config.settings import MAX_FILE_SIZE_MB, SUPPORTED_FILE_TYPES


def validate_file(uploaded_file) -> tuple[bool, str]:
    """
    Validate uploaded file type, size, and empty content.
    Returns:
        (True, "") when valid
        (False, "error message") when invalid
    """

    if uploaded_file is None:
        return False, "Please upload a file first."

    file_extension = Path(uploaded_file.name).suffix.lower()

    if file_extension not in SUPPORTED_FILE_TYPES:
        supported = ", ".join(SUPPORTED_FILE_TYPES)
        return False, f"Unsupported file type. Supported formats: {supported}"

    file_size_mb = uploaded_file.size / (1024 * 1024)

    if file_size_mb > MAX_FILE_SIZE_MB:
        return (
            False,
            f"File is too large. Maximum allowed size is {MAX_FILE_SIZE_MB} MB.",
        )

    if uploaded_file.size == 0:
        return False, "The uploaded file is empty."

    return True, ""