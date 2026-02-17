"""
Бизнес-логика инвентаризации: кампании, пункты, отметка «найдено», формирование объёма проверки.
Все записи в БД (add/flush) — в сервисе; роутеры только вызывают эти функции.
"""
import logging
from datetime import datetime

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import InventoryCampaign, InventoryItem

logger = logging.getLogger(__name__)


async def create_campaign(
    db: AsyncSession,
    name: str,
    description: str | None = None,
    company_id: int | None = None,
) -> InventoryCampaign:
    """Создаёт кампанию инвентаризации. Возвращает объект с id после flush."""
    campaign = InventoryCampaign(
        name=name.strip(),
        description=description.strip() if description else None,
        company_id=company_id,
    )
    db.add(campaign)
    await db.flush()
    return campaign


async def update_campaign(
    db: AsyncSession,
    campaign: InventoryCampaign,
    name: str,
    description: str | None = None,
    company_id: int | None = None,
    started_at: datetime | None = None,
    finished_at: datetime | None = None,
) -> None:
    """Обновляет поля кампании."""
    campaign.name = name.strip()
    campaign.description = description.strip() if description else None
    campaign.company_id = company_id
    campaign.started_at = started_at
    campaign.finished_at = finished_at
    await db.flush()


async def finish_campaign(db: AsyncSession, campaign_id: int) -> bool:
    """Устанавливает finished_at = сейчас. Возвращает True, если кампания найдена и обновлена."""
    from app.repositories import inventory_repo
    campaign = await inventory_repo.get_campaign_by_id(db, campaign_id)
    if not campaign:
        return False
    campaign.finished_at = datetime.utcnow()
    await db.flush()
    logger.info("inventory_campaign_finished campaign_id=%s", campaign_id)
    return True


async def generate_campaign_scope(db: AsyncSession, campaign_id: int) -> int:
    """
    Формирует объём проверки: заменяет пункты кампании списком InventoryItem по активам
    (по company_id кампании или все). Возвращает число добавленных пунктов.
    """
    from app.repositories import inventory_repo
    campaign = await inventory_repo.get_campaign_by_id(db, campaign_id)
    if not campaign:
        raise ValueError("Кампания не найдена")
    await db.execute(delete(InventoryItem).where(InventoryItem.campaign_id == campaign_id))
    await db.flush()
    asset_ids = await inventory_repo.get_asset_ids_for_scope(db, campaign.company_id)
    for aid in asset_ids:
        item = InventoryItem(campaign_id=campaign_id, asset_id=aid)
        db.add(item)
    await db.flush()
    logger.info("inventory_scope_generated campaign_id=%s items_count=%s", campaign_id, len(asset_ids))
    return len(asset_ids)


async def add_campaign_item(
    db: AsyncSession,
    campaign_id: int,
    asset_id: int | None = None,
    expected_location: str | None = None,
    notes: str | None = None,
) -> None:
    """Добавляет пункт в кампанию."""
    item = InventoryItem(
        campaign_id=campaign_id,
        asset_id=asset_id,
        expected_location=expected_location or None,
        notes=notes or None,
    )
    db.add(item)
    await db.flush()


async def mark_item_found_by_id(
    db: AsyncSession,
    campaign_id: int,
    item_id: int,
) -> bool:
    """Отмечает пункт инвентаризации как найденный по id. Возвращает True если пункт найден и обновлён, False если пункт не найден."""
    from app.repositories import inventory_repo
    item = await inventory_repo.get_inventory_item_by_id(db, campaign_id, item_id)
    if not item:
        return False
    item.found = True
    item.found_at = datetime.utcnow()
    await db.flush()
    logger.info("inventory_item_found campaign_id=%s item_id=%s", campaign_id, item_id)
    return True


async def mark_asset_found(
    db: AsyncSession,
    campaign_id: int,
    asset_id: int,
) -> None:
    """Отмечает оборудование найденным в кампании. Создаёт пункт при отсутствии, иначе обновляет found/found_at."""
    item_result = await db.execute(
        select(InventoryItem)
        .where(InventoryItem.campaign_id == campaign_id)
        .where(InventoryItem.asset_id == asset_id)
    )
    item = item_result.scalar_one_or_none()
    if not item:
        item = InventoryItem(
            campaign_id=campaign_id,
            asset_id=asset_id,
            found=True,
            found_at=datetime.utcnow(),
        )
        db.add(item)
    else:
        item.found = True
        item.found_at = datetime.utcnow()
    await db.flush()
    logger.info("inventory_asset_found campaign_id=%s asset_id=%s", campaign_id, asset_id)
