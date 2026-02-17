"""
Unit-тесты: создание/обновление актива и генерация событий (AssetEvent).
Правило: для списанного оборудования запрещено менять location/current_user.
"""
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Asset, AssetEvent
from app.models.asset import AssetStatus, AssetEventType
from app.services import assets_service


@pytest.mark.asyncio
async def test_create_asset_creates_event(db: AsyncSession):
    """Создание актива создаёт запись AssetEvent типа created."""
    data = {
        "name": "Test PC",
        "status": AssetStatus.active,
        "serial_number": "SN-UNIT-001",
    }
    asset = await assets_service.create_asset(db, data, created_by_id=1, event_description="Unit test")
    await db.flush()
    assert asset.id is not None
    result = await db.execute(select(AssetEvent).where(AssetEvent.asset_id == asset.id))
    events = result.scalars().all()
    assert len(events) == 1
    assert events[0].event_type == AssetEventType.created
    assert events[0].description == "Unit test"


@pytest.mark.asyncio
async def test_update_asset_creates_event(db: AsyncSession):
    """Обновление актива создаёт запись AssetEvent типа updated."""
    asset = Asset(name="Asset", status=AssetStatus.active)
    db.add(asset)
    await db.flush()
    changes = [{"field_label": "Расположение", "old": "А-1", "new": "Б-2"}]
    await assets_service.update_asset(
        db, asset, {"location": "Б-2"}, changes=changes, updated_by_id=1
    )
    await db.flush()
    result = await db.execute(select(AssetEvent).where(AssetEvent.asset_id == asset.id))
    events = result.scalars().all()
    assert len(events) == 1
    assert events[0].event_type == AssetEventType.updated
    assert "Расположение" in (events[0].changes_json or "")


@pytest.mark.asyncio
async def test_retired_asset_rejects_location_change(db: AsyncSession):
    """Для актива со статусом retired нельзя изменить location."""
    asset = Asset(name="Retired", status=AssetStatus.retired, location="Old")
    db.add(asset)
    await db.flush()
    with pytest.raises(ValueError, match="Перемещение и выдача запрещены"):
        await assets_service.update_asset(
            db, asset, {"location": "New"}, changes=[], updated_by_id=1
        )


@pytest.mark.asyncio
async def test_retired_asset_rejects_current_user_change(db: AsyncSession):
    """Для актива со статусом retired нельзя изменить current_user."""
    asset = Asset(name="Retired", status=AssetStatus.retired, current_user="Old")
    db.add(asset)
    await db.flush()
    with pytest.raises(ValueError, match="Перемещение и выдача запрещены"):
        await assets_service.update_asset(
            db, asset, {"current_user": "New"}, changes=[], updated_by_id=1
        )


@pytest.mark.asyncio
async def test_add_asset_event_creates_record(db: AsyncSession):
    """add_asset_event добавляет запись в журнал событий."""
    asset = Asset(name="A", status=AssetStatus.active)
    db.add(asset)
    await db.flush()
    await assets_service.add_asset_event(
        db, asset.id, AssetEventType.moved, "Перемещение в офис", created_by_id=1
    )
    await db.flush()
    result = await db.execute(select(AssetEvent).where(AssetEvent.asset_id == asset.id))
    events = result.scalars().all()
    assert len(events) == 1
    assert events[0].event_type == AssetEventType.moved
    assert events[0].description == "Перемещение в офис"
