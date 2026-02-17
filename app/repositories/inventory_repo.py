"""
Доступ к данным инвентаризации: кампании, пункты (InventoryItem).
"""
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Asset, InventoryCampaign, InventoryItem


async def get_campaigns_count(db: AsyncSession) -> int:
    """Общее количество кампаний инвентаризации."""
    r = await db.execute(select(func.count(InventoryCampaign.id)))
    return r.scalar() or 0


async def get_campaign_by_id(db: AsyncSession, campaign_id: int) -> InventoryCampaign | None:
    """Кампания по id."""
    result = await db.execute(select(InventoryCampaign).where(InventoryCampaign.id == campaign_id))
    return result.scalar_one_or_none()


async def get_campaign_with_items(
    db: AsyncSession,
    campaign_id: int,
) -> InventoryCampaign | None:
    """Кампания по id с загрузкой items и asset у каждого item."""
    result = await db.execute(
        select(InventoryCampaign)
        .where(InventoryCampaign.id == campaign_id)
        .options(selectinload(InventoryCampaign.items).selectinload(InventoryItem.asset))
    )
    return result.scalar_one_or_none()


async def get_inventory_item(
    db: AsyncSession,
    campaign_id: int,
    asset_id: int,
) -> InventoryItem | None:
    """Пункт инвентаризации по кампании и активу."""
    result = await db.execute(
        select(InventoryItem)
        .where(InventoryItem.campaign_id == campaign_id)
        .where(InventoryItem.asset_id == asset_id)
    )
    return result.scalar_one_or_none()


async def get_inventory_item_by_id(
    db: AsyncSession,
    campaign_id: int,
    item_id: int,
) -> InventoryItem | None:
    """Пункт инвентаризации по id в рамках кампании."""
    result = await db.execute(
        select(InventoryItem)
        .where(InventoryItem.id == item_id)
        .where(InventoryItem.campaign_id == campaign_id)
    )
    return result.scalar_one_or_none()


async def get_asset_counts_by_company(db: AsyncSession) -> dict[int | None, int]:
    """Количество активов по company_id (для отображения в списке инвентаризации)."""
    result = await db.execute(
        select(Asset.company_id, func.count(Asset.id))
        .where(Asset.company_id.isnot(None))
        .group_by(Asset.company_id)
    )
    return dict(result.all())


async def get_campaigns_without_company(db: AsyncSession) -> list[InventoryCampaign]:
    """Кампании без привязки к организации, по убыванию started_at."""
    result = await db.execute(
        select(InventoryCampaign)
        .where(InventoryCampaign.company_id.is_(None))
        .order_by(InventoryCampaign.started_at.desc())
    )
    return list(result.scalars().all())


async def get_all_assets_ordered(db: AsyncSession) -> list[Asset]:
    """Все активы по имени (для выбора в форме кампании и т.д.)."""
    result = await db.execute(select(Asset).order_by(Asset.name))
    return list(result.scalars().all())


async def get_active_campaigns(db: AsyncSession) -> list[InventoryCampaign]:
    """Незавершённые кампании (finished_at is None), по убыванию started_at (для страницы сканирования)."""
    result = await db.execute(
        select(InventoryCampaign)
        .where(InventoryCampaign.finished_at.is_(None))
        .order_by(InventoryCampaign.started_at.desc())
    )
    return list(result.scalars().all())


async def get_asset_ids_for_scope(db: AsyncSession, company_id: int | None) -> list[int]:
    """
    Список id активов для объёма проверки кампании.
    Если company_id задан — только активы этой организации; иначе все активы (по имени).
    """
    q = select(Asset.id).order_by(Asset.name)
    if company_id is not None:
        q = q.where(Asset.company_id == company_id)
    result = await db.execute(q)
    return [r[0] for r in result.all()]
