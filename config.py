import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATABASE_PATH = DATA_DIR / "inventory.db"

UPLOAD_FOLDER = BASE_DIR / "uploads"
THUMBNAIL_FOLDER = UPLOAD_FOLDER / "thumbnails"
DOCUMENT_FOLDER = UPLOAD_FOLDER / "documents"

STATIC_DIR = BASE_DIR / "static"
LOG_DIR = BASE_DIR / "log"
LOG_FILE = LOG_DIR / "backend.log"
FRONTEND_LOG_FILE = LOG_DIR / "frontend.log"

HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "5000"))
SERVER_URL = os.environ.get("SERVER_URL", "http://localhost:5000")
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")
API_TOKEN = os.environ.get("API_TOKEN", "")
API_TOKEN_REQUIRE_ALL = os.environ.get("API_TOKEN_REQUIRE_ALL", "").lower() in {"1", "true", "yes"}
MAX_CONTENT_LENGTH = 16 * 1024 * 1024
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
ALLOWED_DOCUMENT_EXTENSIONS = {
    ".pdf",
    ".txt",
    ".md",
    ".csv",
    ".xls",
    ".xlsx",
    ".doc",
    ".docx",
    ".ppt",
    ".pptx",
    ".zip",
}


def ensure_runtime_directories() -> None:
    for path in (DATA_DIR, UPLOAD_FOLDER, THUMBNAIL_FOLDER, DOCUMENT_FOLDER, LOG_DIR):
        path.mkdir(parents=True, exist_ok=True)
