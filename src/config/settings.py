import os

from dotenv import load_dotenv

from src.config.runtime_paths import ENV_FILE, OUTPUT_DIR, RESOURCE_DIR

BASE_DIR = RESOURCE_DIR

load_dotenv(ENV_FILE)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_CHUNK_MODEL = os.getenv("OPENAI_CHUNK_MODEL", "gpt-5-mini")
NOTION_API_KEY = os.getenv("NOTION_API_KEY", "")
NOTION_PARENT_PAGE_ID = os.getenv("NOTION_PARENT_PAGE_ID", "")
OPENAI_MERGE_MODEL = os.getenv("OPENAI_MERGE_MODEL", "gpt-5")
OPENAI_MODEL = OPENAI_CHUNK_MODEL

MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "25"))
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "6000"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "500"))

SUPPORTED_FILE_TYPES = [".pdf", ".docx", ".txt", ".md"]

APP_AUTO_DOWNLOAD_UPDATES = (
    os.getenv("APP_AUTO_DOWNLOAD_UPDATES", "false").strip().lower()
    in {"1", "true", "yes", "on"}
)
