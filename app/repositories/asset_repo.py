"""
Доступ к данным активов: выборки по фильтрам, по id, справочные списки (локации, серийники), сводки.
"""
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Asset, AssetEvent, Company
from app.models.asset import AssetStatus, EquipmentKind

# Типы техники для отчёта «Светофор» — только enum
TRAFFIC_LIGHT_KINDS = (EquipmentKind.desktop, EquipmentKind.nettop, EquipmentKind.laptop, EquipmentKind.server)


def _build_list_query(
    name: str | None,
    status: str | None,
    inactive_by_activity: bool,
    equipment_kind: str | None,
    location: str | None,
    company_id: str | None,
    sort: str = "newest",
):
    """Собирает запрос списка активов с фильтрами (для списка и экспорта)."""
    status_filter = None
    if status and status.strip() and status.strip() in ("active", "inactive", "maintenance", "retired"):
        status_filter = AssetStatus(status.strip())
    q = select(Asset).options(selectinload(Asset.company)).where(Asset.deleted_at.is_(None))
    if sort == "oldest":
        q = q.order_by(Asset.created_at.asc(), Asset.id.asc())
    else:
        q = q.order_by(Asset.created_at.desc(), Asset.id.desc())
    if name:
        q = q.where(Asset.name.ilike(f"%{name}%"))
    if inactive_by_activity:
        q = q.where(Asset.status != AssetStatus.retired)
    elif status_filter is not None:
        q = q.where(Asset.status == status_filter)
    if equipment_kind:
        try:
            q = q.where(Asset.equipment_kind == EquipmentKind(equipment_kind))
        except ValueError:
            pass
    if location and location.strip():
        q = q.where(Asset.location == location.strip())
    if company_id and company_id.strip():
        try:
            q = q.where(Asset.company_id == int(company_id.strip()))
        except ValueError:
            pass
    return q


async def get_assets_list(
    db: AsyncSession,
    name: str | None = None,
    status: str | None = None,
    inactive_by_activity: bool = False,
    equipment_kind: str | None = None,
    location: str | None = None,
    company_id: str | None = None,
    sort: str = "newest",
) -> list[Asset]:
    """Возвращает список активов с загрузкой company по заданным фильтрам."""
    q = _build_list_query(name, status, inactive_by_activity, equipment_kind, location, company_id, sort)
    result = await db.execute(q)
    return list(result.scalars().all())


async def advanced_search_assets(
    db: AsyncSession,
    name: str | None = None,
    status: str | None = None,
    equipment_kind: str | None = None,
    location: str | None = None,
    company_id: str | None = None,
    current_user: str | None = None,
    cpu: str | None = None,
    ram: str | None = None,
    disk1_type: str | None = None,
    disk1_capacity: str | None = None,
    network_card: str | None = None,
    motherboard: str | None = None,
    os: str | None = None,
    description: str | None = None,
    screen_diagonal: str | None = None,
    screen_resolution: str | None = None,
    monitor_diagonal: str | None = None,
    power_supply: str | None = None,
    rack_units: str | None = None,
    manufacture_date_from=None,
    manufacture_date_to=None,
) -> list[Asset]:
    """
    Расширенный поиск по оборудованию: позволяет комбинировать базовые фильтры
    (название, статус, тип техники, расположение, организация) с техническими полями.
    """
    status_filter = None
    if status and status.strip() and status.strip() in ("active", "inactive", "maintenance", "retired"):
        status_filter = AssetStatus(status.strip())
    q = select(Asset).options(selectinload(Asset.company)).where(Asset.deleted_at.is_(None))
    if name:
        q = q.where(Asset.name.ilike(f"%{name}%"))
    if status_filter is not None:
        q = q.where(Asset.status == status_filter)
    if equipment_kind:
        try:
            q = q.where(Asset.equipment_kind == EquipmentKind(equipment_kind))
        except ValueError:
            pass
    if location and location.strip():
        q = q.where(Asset.location.ilike(f"%{location.strip()}%"))
    if company_id and company_id.strip():
        try:
            q = q.where(Asset.company_id == int(company_id.strip()))
        except ValueError:
            pass
    if current_user and current_user.strip():
        q = q.where(Asset.current_user.ilike(f"%{current_user.strip()}%"))
    if cpu and cpu.strip():
        q = q.where(Asset.cpu.ilike(f"%{cpu.strip()}%"))
    if ram and ram.strip():
        q = q.where(Asset.ram.ilike(f"%{ram.strip()}%"))
    if disk1_type and disk1_type.strip():
        q = q.where(Asset.disk1_type.ilike(f"%{disk1_type.strip()}%"))
    if disk1_capacity and disk1_capacity.strip():
        q = q.where(Asset.disk1_capacity.ilike(f"%{disk1_capacity.strip()}%"))
    if network_card and network_card.strip():
        q = q.where(Asset.network_card.ilike(f"%{network_card.strip()}%"))
    if motherboard and motherboard.strip():
        q = q.where(Asset.motherboard.ilike(f"%{motherboard.strip()}%"))
    if os and os.strip():
        q = q.where(Asset.os == os.strip())
    if description and description.strip():
        q = q.where(Asset.description.ilike(f"%{description.strip()}%"))
    if screen_diagonal and screen_diagonal.strip():
        q = q.where(Asset.screen_diagonal.ilike(f"%{screen_diagonal.strip()}%"))
    if screen_resolution and screen_resolution.strip():
        q = q.where(Asset.screen_resolution.ilike(f"%{screen_resolution.strip()}%"))
    if monitor_diagonal and monitor_diagonal.strip():
        q = q.where(Asset.monitor_diagonal.ilike(f"%{monitor_diagonal.strip()}%"))
    if power_supply and power_supply.strip():
        q = q.where(Asset.power_supply.ilike(f"%{power_supply.strip()}%"))
    if rack_units is not None and str(rack_units).strip() != "":
        try:
            q = q.where(Asset.rack_units == int(rack_units))
        except ValueError:
            pass
    if manufacture_date_from is not None:
        q = q.where(Asset.manufacture_date >= manufacture_date_from)
    if manufacture_date_to is not None:
        q = q.where(Asset.manufacture_date <= manufacture_date_to)
    q = q.order_by(Asset.created_at.desc(), Asset.id.desc())
    result = await db.execute(q)
    return list(result.scalars().all())


async def get_asset_by_id(db: AsyncSession, asset_id: int) -> Asset | None:
    """Актив по id без связей."""
    result = await db.execute(select(Asset).where(Asset.id == asset_id))
    return result.scalar_one_or_none()


async def get_asset_by_id_with_relations(
    db: AsyncSession,
    asset_id: int,
) -> Asset | None:
    """Актив по id с загрузкой events, company, inventory_items."""
    result = await db.execute(
        select(Asset)
        .where(Asset.id == asset_id)
        .options(
            selectinload(Asset.events),
            selectinload(Asset.company),
            selectinload(Asset.inventory_items),
        )
    )
    return result.scalar_one_or_none()


async def get_distinct_locations(db: AsyncSession) -> list[str]:
    """Список уникальных непустых расположений для фильтра (без удалённых)."""
    result = await db.execute(
        select(Asset.location)
        .where(Asset.deleted_at.is_(None))
        .where(Asset.location.isnot(None))
        .where(Asset.location != "")
        .distinct()
        .order_by(Asset.location)
    )
    return [r[0] for r in result.all()]


async def get_existing_serial_numbers(db: AsyncSession) -> set[str]:
    """Множество серийных номеров, уже существующих в БД (без удалённых)."""
    result = await db.execute(
        select(Asset.serial_number)
        .where(Asset.deleted_at.is_(None))
        .where(Asset.serial_number.isnot(None))
        .where(Asset.serial_number != "")
    )
    return {r[0] for r in result.all()}


async def get_traffic_light_assets(
    db: AsyncSession,
    company_id: int | None = None,
) -> list[Asset]:
    """Активы для отчёта «Светофор» (типы desktop, nettop, laptop, server), с company, без удалённых."""
    q = (
        select(Asset)
        .where(Asset.deleted_at.is_(None))
        .where(Asset.equipment_kind.in_(TRAFFIC_LIGHT_KINDS))
        .options(selectinload(Asset.company))
        .order_by(Asset.company_id, Asset.name)
    )
    if company_id is not None:
        q = q.where(Asset.company_id == company_id)
    result = await db.execute(q)
    return list(result.scalars().all())


async def get_total_assets_count(db: AsyncSession) -> int:
    """Общее количество активов (без удалённых)."""
    r = await db.execute(select(func.count(Asset.id)).where(Asset.deleted_at.is_(None)))
    return r.scalar() or 0


async def get_asset_status_counts(db: AsyncSession) -> dict:
    """Словарь статус -> количество активов (для отчётов/дашборда), без удалённых."""
    result = await db.execute(
        select(Asset.status, func.count(Asset.id)).where(Asset.deleted_at.is_(None)).group_by(Asset.status)
    )
    return dict(result.all())


async def get_all_assets_ordered_by_id(db: AsyncSession) -> list[Asset]:
    """Все активы, упорядоченные по id (для дашборда, без удалённых)."""
    result = await db.execute(select(Asset).where(Asset.deleted_at.is_(None)).order_by(Asset.id))
    return list(result.scalars().all())


async def get_company_asset_summary(
    db: AsyncSession, company_id: int
) -> dict:
    """Сводка по технике организации: total, status_counts, location_counts."""
    total = (
        await db.execute(
            select(func.count(Asset.id)).where(Asset.company_id == company_id).where(Asset.deleted_at.is_(None))
        )
    ).scalar() or 0
    by_status = await db.execute(
        select(Asset.status, func.count(Asset.id))
        .where(Asset.company_id == company_id)
        .where(Asset.deleted_at.is_(None))
        .group_by(Asset.status)
    )
    status_counts = dict(by_status.all())
    by_location = await db.execute(
        select(Asset.location, func.count(Asset.id))
        .where(Asset.company_id == company_id)
        .where(Asset.deleted_at.is_(None))
        .where(Asset.location.isnot(None))
        .where(Asset.location != "")
        .group_by(Asset.location)
        .order_by(func.count(Asset.id).desc())
        .limit(20)
    )
    location_counts = list(by_location.all())
    return {"total": total, "status_counts": status_counts, "location_counts": location_counts}


async def get_recent_asset_events(db: AsyncSession, limit: int = 500) -> list[AssetEvent]:
    """Последние события по активам с загрузкой актива (для страницы перемещений)."""
    result = await db.execute(
        select(AssetEvent)
        .options(selectinload(AssetEvent.asset))
        .order_by(AssetEvent.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())
