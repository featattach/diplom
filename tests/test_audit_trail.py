"""
Тест audit trail: изменение критичных полей актива создаёт запись AssetEvent.
"""
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Asset, AssetEvent
from app.models.asset import AssetStatus
from app.services import assets_service


@pytest.mark.asyncio
async def test_any_asset_update_creates_asset_event(db: AsyncSession):
    """
    Любое обновление актива через update_asset создаёт событие AssetEvent типа updated.
    Audit trail: в БД остаётся след изменения.
    """
    asset = Asset(name="Audit Asset", status=AssetStatus.active, location="Room A")
    db.add(asset)
    await db.flush()
    initial_count = (await db.execute(select(AssetEvent).where(AssetEvent.asset_id == asset.id))).scalars().all()
    assert len(initial_count) == 0

    await assets_service.update_asset(
        db,
        asset,
        {"location": "Room B", "description": "Moved"},
        changes=[{"field_label": "Расположение", "old": "Room A", "new": "Room B"}],
        updated_by_id=1,
    )
    await db.flush()

    events = (await db.execute(select(AssetEvent).where(AssetEvent.asset_id == asset.id))).scalars().all()
    assert len(events) == 1
    assert events[0].event_type.value == "updated"
    assert events[0].changes_json is not None
    assert "Room A" in events[0].changes_json
    assert "Room B" in events[0].changes_json
