"""
Интеграционные тесты: эндпоинты CRUD (список активов, экспорт).
"""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_assets_list_requires_auth(client_anon: AsyncClient):
    """Без авторизации список активов возвращает 302 на логин или 401."""
    r = await client_anon.get("/assets")
    assert r.status_code in (302, 401)


@pytest.mark.asyncio
async def test_assets_list_ok(client: AsyncClient):
    """С авторизацией GET /assets возвращает 200."""
    r = await client.get("/assets")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_reports_page_ok(client: AsyncClient):
    """Страница отчётов доступна авторизованному пользователю."""
    r = await client.get("/reports")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_equipment_export_ok(client: AsyncClient):
    """Экспорт оборудования в Excel возвращает 200 и xlsx."""
    r = await client.get("/reports/equipment/export.xlsx")
    assert r.status_code == 200
    ct = r.headers.get("content-type", "").lower()
    cd = r.headers.get("content-disposition", "").lower()
    assert "spreadsheet" in ct or "xlsx" in cd
