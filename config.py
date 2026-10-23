"""Configuration settings for ClauseLens."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# Server
HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "5000"))
DEBUG = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")
SECRET_KEY = os.getenv("SECRET_KEY", "clauselens-secure-local-session-secret-key-2026")

# Database & Storage
DATABASE_PATH = os.getenv("DATABASE_PATH", str(BASE_DIR / "clauselens.db"))
TEMP_UPLOAD_DIR = BASE_DIR / "temp_uploads"
TEMP_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Upload limits
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "15"))
MAX_CONTENT_LENGTH = MAX_UPLOAD_MB * 1024 * 1024

# Data retention & scanning thresholds
RETENTION_DAYS = int(os.getenv("RETENTION_DAYS", "30"))
SCANNED_THRESHOLD = int(os.getenv("SCANNED_THRESHOLD", "100"))

# Nemotron P2 integration settings
NEMOTRON_ENABLED = os.getenv("NEMOTRON_ENABLED", "false").lower() in ("true", "1", "yes")
NEMOTRON_BASE_URL = os.getenv("NEMOTRON_BASE_URL", "").rstrip("/")
NEMOTRON_API_KEY = os.getenv("NEMOTRON_API_KEY", "")
NEMOTRON_MODEL = os.getenv("NEMOTRON_MODEL", "")
NEMOTRON_TIMEOUT = int(os.getenv("NEMOTRON_TIMEOUT", "20"))

APP_VERSION = "1.0.0"
