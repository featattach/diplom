"""История/журнал по активам: добавление событий (AssetEvent)."""
from fastapi import APIRouter, Depends, Form, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.asset import AssetEventType, AssetStatus
from app.auth import require_role
from app.models.user import User, UserRole
from app.repositories import asset_repo
from app.services.assets_service import add_asset_event

router = APIRouter(prefix="", tags=["assets_events"])

MOVE_EVENT_TYPES = (AssetEventType.moved, AssetEventType.assigned, AssetEventType.returned)


@router.post("/assets/{asset_id:int}/event", name="asset_add_event", include_in_schema=False)
async def asset_add_event_handler(
    asset_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin, UserRole.user)),
    event_type: AssetEventType = Form(...),
    description: str | None = Form(None),
):
    asset = await asset_repo.get_asset_by_id(db, asset_id)
    if not asset:
        raise HTTPException(404, "Asset not found")
    if asset.status == AssetStatus.retired and event_type in MOVE_EVENT_TYPES:
        raise HTTPException(400, "Для списанного оборудования нельзя добавлять перемещение, выдачу или возврат.")
    await add_asset_event(db, asset_id, event_type, description or "", current_user.id)
    return RedirectResponse(url=f"/assets/{asset_id}", status_code=302)
