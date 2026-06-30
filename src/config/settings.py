from pathlib import Path
import os

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[2]

load_dotenv(BASE_DIR / ".env")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_CHUNK_MODEL = os.getenv("OPENAI_CHUNK_MODEL", "gpt-5-mini")
NOTION_API_KEY = os.getenv("NOTION_API_KEY", "")
NOTION_PARENT_PAGE_ID = os.getenv("NOTION_PARENT_PAGE_ID", "")
OPENAI_MERGE_MODEL = os.getenv("OPENAI_MERGE_MODEL", "gpt-5")
OPENAI_MODEL = OPENAI_CHUNK_MODEL

MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "10"))
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "6000"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "500"))

SUPPORTED_FILE_TYPES = [".pdf", ".docx", ".txt", ".md"]
OUTPUT_DIR = BASE_DIR / "outputs"
