"""
Общие фикстуры: тестовая БД (SQLite in-memory), сессия, клиент с авторизацией.
"""
import asyncio
from collections.abc import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.database import Base, get_db
from app.main import app
from app.models import User
from app.models.user import UserRole
from app.auth import create_session_token
from app.config import SESSION_COOKIE_NAME

# In-memory SQLite для тестов (один engine на весь прогон)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
)
TestSessionLocal = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


@pytest_asyncio.fixture
async def create_tables():
    """Создание таблиц в тестовой БД (function scope — совместимо с pytest-asyncio)."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@pytest_asyncio.fixture
async def db(create_tables) -> AsyncGenerator[AsyncSession, None]:
    """Сессия БД с откатом после теста (отдельное соединение, откат в конце)."""
    from werkzeug.security import generate_password_hash
    async with test_engine.connect() as conn:
        await conn.begin()
        async with AsyncSession(bind=conn, expire_on_commit=False) as session:
            user = User(
                username="unituser",
                password_hash=generate_password_hash("x"),
                role=UserRole.user,
                is_active=True,
            )
            session.add(user)
            await session.flush()
            yield session
        await conn.rollback()


@pytest_asyncio.fixture
async def db_commit(create_tables) -> AsyncGenerator[AsyncSession, None]:
    """Сессия БД с коммитом (данные видны в последующих запросах приложения)."""
    async with TestSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@pytest_asyncio.fixture
async def test_user(db_commit: AsyncSession) -> User:
    """Пользователь admin в БД (get_or_create: в in-memory БД данные сохраняются между тестами)."""
    from sqlalchemy import select
    from werkzeug.security import generate_password_hash
    r = await db_commit.execute(select(User).where(User.username == "testadmin"))
    u = r.scalar_one_or_none()
    if u:
        return u
    user = User(
        username="testadmin",
        password_hash=generate_password_hash("testpass"),
        role=UserRole.admin,
        is_active=True,
    )
    db_commit.add(user)
    await db_commit.flush()
    await db_commit.commit()
    async with TestSessionLocal() as s:
        r2 = await s.execute(select(User).where(User.username == "testadmin"))
        return r2.scalar_one()


async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
    async with TestSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@pytest_asyncio.fixture
async def client(db_commit, test_user) -> AsyncGenerator[AsyncClient, None]:
    """HTTP-клиент с подменой get_db и авторизацией под test_user."""
    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as ac:
            # Установить cookie сессии для авторизации
            token = create_session_token(test_user.id)
            ac.cookies.set(SESSION_COOKIE_NAME, token)
            yield ac
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest_asyncio.fixture
async def client_anon(db_commit) -> AsyncGenerator[AsyncClient, None]:
    """Клиент без авторизации (get_db подменён)."""
    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as ac:
            yield ac
    finally:
        app.dependency_overrides.pop(get_db, None)
