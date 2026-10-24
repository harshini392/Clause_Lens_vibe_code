"""Configuration settings for ClauseSight."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# Load .env file if present
_env_path = BASE_DIR / ".env"
if _env_path.is_file():
    try:
        with open(_env_path, "r", encoding="utf-8") as _f:
            for _line in _f:
                _line = _line.strip()
                if _line and not _line.startswith("#") and "=" in _line:
                    _k, _v = _line.split("=", 1)
                    os.environ.setdefault(_k.strip(), _v.strip())
    except Exception:
        pass

# Server
HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "5000"))
DEBUG = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")
SECRET_KEY = os.getenv("SECRET_KEY", "clausesight-secure-local-session-secret-key-2026")

# Database & Storage
_legacy_db = BASE_DIR / "clauselens.db"
_default_db = BASE_DIR / "clausesight.db"
_db_default = str(_default_db if _default_db.exists() or not _legacy_db.exists() else _legacy_db)
DATABASE_PATH = os.getenv("DATABASE_PATH", _db_default)
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
