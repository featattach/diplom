"""
Создание и восстановление бекапов: БД (app.db), папки avatars и qrcodes.
Бекап — один zip-файл в data/backups/ с именем backup_YYYY-MM-DD_HH-MM-SS.zip.
"""
from __future__ import annotations

import shutil
import zipfile
from datetime import datetime
from pathlib import Path

from app.config import BACKUP_DIR, DATA_DIR, DB_PATH, AVATAR_DIR, QR_DIR


def _ensure_backup_dir() -> None:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)


def create_backup() -> str:
    """
    Создаёт zip-бекап: app.db, avatars/, qrcodes/.
    Возвращает имя файла бекапа (например backup_2026-02-09_12-30-00.zip).
    """
    _ensure_backup_dir()
    name = f"backup_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.zip"
    path = BACKUP_DIR / name
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        if DB_PATH.exists():
            zf.write(DB_PATH, "app.db")
        if AVATAR_DIR.exists():
            for f in AVATAR_DIR.iterdir():
                if f.is_file():
                    zf.write(f, f"avatars/{f.name}")
        if QR_DIR.exists():
            for f in QR_DIR.iterdir():
                if f.is_file():
                    zf.write(f, f"qrcodes/{f.name}")
    return name


def list_backups() -> list[dict]:
    """
    Список бекапов: [{name, size_bytes, mtime}, ...], по дате создания (новые первые).
    """
    _ensure_backup_dir()
    out = []
    for f in sorted(BACKUP_DIR.glob("backup_*.zip"), key=lambda p: p.stat().st_mtime, reverse=True):
        st = f.stat()
        out.append({
            "name": f.name,
            "size_bytes": st.st_size,
            "mtime": datetime.fromtimestamp(st.st_mtime),
        })
    return out


def get_backup_path(filename: str) -> Path | None:
    """Путь к файлу бекапа, если он существует и имя безопасное."""
    if not filename or ".." in filename or not filename.endswith(".zip"):
        return None
    if not filename.startswith("backup_"):
        return None
    path = BACKUP_DIR / filename
    return path if path.is_file() else None


def restore_backup(filename: str) -> None:
    """
    Восстанавливает данные из бекапа: распаковывает во временную папку,
    затем копирует app.db, содержимое avatars и qrcodes в data/.
    Перед вызовом желательно закрыть соединения с БД (engine.dispose()).
    """
    path = get_backup_path(filename)
    if not path:
        raise ValueError("Недопустимое имя бекапа или файл не найден")
    import tempfile
    with tempfile.TemporaryDirectory(prefix="vkr_restore_") as tmp:
        tmp_path = Path(tmp)
        with zipfile.ZipFile(path, "r") as zf:
            zf.extractall(tmp_path)
        # app.db
        db_src = tmp_path / "app.db"
        if db_src.exists():
            shutil.copy2(db_src, DB_PATH)
        # avatars
        avatars_src = tmp_path / "avatars"
        if avatars_src.exists():
            AVATAR_DIR.mkdir(parents=True, exist_ok=True)
            for f in avatars_src.iterdir():
                if f.is_file():
                    shutil.copy2(f, AVATAR_DIR / f.name)
        # qrcodes
        qrcodes_src = tmp_path / "qrcodes"
        if qrcodes_src.exists():
            QR_DIR.mkdir(parents=True, exist_ok=True)
            for f in qrcodes_src.iterdir():
                if f.is_file():
                    shutil.copy2(f, QR_DIR / f.name)
