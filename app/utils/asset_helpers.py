"""Общие хелперы для работы с активами (используются отчётами и роутерами)."""
from datetime import datetime, timedelta

from app.config import INACTIVE_DAYS_THRESHOLD
from app.models import Asset


def is_asset_inactive(asset: Asset) -> bool:
    """True, если у актива нет last_seen_at или он старше INACTIVE_DAYS_THRESHOLD."""
    if not asset.last_seen_at:
        return True
    threshold = datetime.utcnow() - timedelta(days=INACTIVE_DAYS_THRESHOLD)
    return asset.last_seen_at.replace(tzinfo=None) < threshold
