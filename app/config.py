import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Use SQLite by default; override with DATABASE_URL env
# Path with forward slashes so SQLite URL works on Windows
_db_path = (BASE_DIR / "data" / "app.db").resolve()
_default_url = f"sqlite+aiosqlite:///{_db_path.as_posix()}"
DATABASE_URL = os.getenv("DATABASE_URL", _default_url)

# Sync URL for Alembic (SQLite)
SYNC_DATABASE_URL = DATABASE_URL.replace("+aiosqlite", "").replace("+asyncpg", "")

SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production-secret-key-32chars")
SESSION_COOKIE_NAME = "session"
INACTIVE_DAYS_THRESHOLD = int(os.getenv("INACTIVE_DAYS_THRESHOLD", "30"))

# Папка для загруженных аватарок (относительно BASE_DIR)
AVATAR_DIR = BASE_DIR / "data" / "avatars"
ALLOWED_AVATAR_EXTENSIONS = {"jpg", "jpeg", "png", "gif", "webp"}
MAX_AVATAR_SIZE_MB = 5

# Папка для сгенерированных QR-кодов оборудования
QR_DIR = BASE_DIR / "data" / "qrcodes"
