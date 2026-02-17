"""
Справочные данные: компании, пользователи (для форм и фильтров).
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Company


async def get_companies_ordered(db: AsyncSession) -> list[Company]:
    """Список всех организаций, отсортированный по имени."""
    result = await db.execute(select(Company).order_by(Company.name))
    return list(result.scalars().all())


async def get_companies_with_campaigns(db: AsyncSession) -> list[Company]:
    """Организации с загруженными кампаниями (для списка инвентаризации)."""
    result = await db.execute(
        select(Company).order_by(Company.name).options(selectinload(Company.campaigns))
    )
    return list(result.scalars().all())


async def get_company_by_id(db: AsyncSession, company_id: int) -> Company | None:
    """Организация по id."""
    result = await db.execute(select(Company).where(Company.id == company_id))
    return result.scalar_one_or_none()


async def find_company_by_name(db: AsyncSession, name: str) -> Company | None:
    """Организация по имени (ilike)."""
    if not name or not name.strip():
        return None
    result = await db.execute(select(Company).where(Company.name.ilike(name.strip())))
    return result.scalar_one_or_none()
