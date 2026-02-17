"""
Загрузка и генерация вложений: QR-коды, аватарки (проверка типов и размеров).
"""
from pathlib import Path

from app.config import QR_DIR


def generate_qr_for_asset(asset_id: int, base_url: str) -> Path:
    """
    Генерирует PNG QR-кода с ссылкой на карточку актива, сохраняет в data/qrcodes.
    Возвращает путь к файлу.
    """
    import qrcode
    QR_DIR.mkdir(parents=True, exist_ok=True)
    url = f"{base_url.rstrip('/')}/assets/{asset_id}"
    qr = qrcode.QRCode(version=1, box_size=8, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    path = QR_DIR / f"{asset_id}.png"
    img.save(path, "PNG")
    return path


def get_qr_path(asset_id: int) -> Path:
    """Возвращает путь к файлу QR-кода актива (без проверки существования)."""
    return QR_DIR / f"{asset_id}.png"
