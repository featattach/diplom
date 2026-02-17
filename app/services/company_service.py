"""
Бизнес-логика организаций (Company): создание, обновление, удаление.
Записи в БД выполняются в сервисе; роутеры только вызывают эти функции.
"""
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Company


async def create_company(
    db: AsyncSession,
    name: str,
    short_info: str | None = None,
) -> Company:
    """Создаёт организацию. Возвращает объект с id после flush."""
    company = Company(
        name=name.strip(),
        short_info=short_info.strip() if short_info else None,
    )
    db.add(company)
    await db.flush()
    return company


async def update_company(
    db: AsyncSession,
    company: Company,
    name: str,
    short_info: str | None = None,
) -> None:
    """Обновляет поля организации."""
    company.name = name.strip()
    company.short_info = (short_info or "").strip() or None
    await db.flush()


async def delete_company(db: AsyncSession, company: Company) -> None:
    """Удаляет организацию из БД."""
    await db.delete(company)
    await db.flush()
