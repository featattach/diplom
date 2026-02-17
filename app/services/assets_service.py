"""
Бизнес-логика активов: создание, обновление с обязательной записью события (AssetEvent).
Роутер передаёт подготовленные данные; сервис выполняет сохранение и создание событий.
"""
import json
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Asset, AssetEvent
from app.models.asset import AssetEventType, AssetStatus

logger = logging.getLogger(__name__)


async def create_asset(
    db: AsyncSession,
    data: dict,
    created_by_id: int,
    event_description: str | None = None,
) -> Asset:
    """
    Создаёт актив и запись события «Создание».
    Возвращает созданный Asset (после flush у него есть id).
    event_description — описание события (по умолчанию "Asset created", для импорта — "Импорт из Excel").
    """
    asset = Asset(**data)
    db.add(asset)
    await db.flush()
    event = AssetEvent(
        asset_id=asset.id,
        event_type=AssetEventType.created,
        description=event_description or "Asset created",
        created_by_id=created_by_id,
    )
    db.add(event)
    await db.flush()
    logger.info("asset_created asset_id=%s name=%s created_by_id=%s", asset.id, getattr(asset, "name", ""), created_by_id)
    return asset


async def update_asset(
    db: AsyncSession,
    asset: Asset,
    data: dict,
    changes: list[dict],
    updated_by_id: int,
) -> None:
    """
    Обновляет поля актива из data и создаёт событие «Изменение» с changes_json.
    changes — список {field_label, old, new} для журнала «было → стало».
    Выдача/перемещение (location, current_user) запрещены для статуса «Списано» (3.2).
    """
    if asset.status == AssetStatus.retired:
        for key in ("location", "current_user"):
            if key in data and getattr(asset, key, None) != data.get(key):
                raise ValueError("Перемещение и выдача запрещены для списанного оборудования")
    for key, value in data.items():
        setattr(asset, key, value)
    await db.flush()
    event = AssetEvent(
        asset_id=asset.id,
        event_type=AssetEventType.updated,
        description="Изменение карточки" if changes else "Asset updated",
        created_by_id=updated_by_id,
        changes_json=json.dumps(changes, ensure_ascii=False) if changes else None,
    )
    db.add(event)
    await db.flush()
    logger.info("asset_updated asset_id=%s updated_by_id=%s", asset.id, updated_by_id)


async def add_asset_event(
    db: AsyncSession,
    asset_id: int,
    event_type: AssetEventType,
    description: str,
    created_by_id: int,
) -> None:
    """Добавляет запись в журнал событий актива."""
    event = AssetEvent(
        asset_id=asset_id,
        event_type=event_type,
        description=description or "",
        created_by_id=created_by_id,
    )
    db.add(event)
    await db.flush()
    logger.info("asset_event asset_id=%s event_type=%s created_by_id=%s", asset_id, event_type.value, created_by_id)
