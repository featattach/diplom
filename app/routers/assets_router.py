from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Request, Query, Form
from fastapi.responses import RedirectResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import INACTIVE_DAYS_THRESHOLD
from app.database import get_db
from app.models import Asset, AssetEvent
from app.models.asset import AssetStatus, AssetEventType
from app.auth import require_user
from app.models.user import User
from app.templates_ctx import templates
from app.services.export_xlsx import export_assets_xlsx

router = APIRouter(prefix="", tags=["assets"])

STATUS_LABELS = {
    "active": "Активно",
    "inactive": "Неактивно",
    "maintenance": "На обслуживании",
    "retired": "Списано",
}
EVENT_TYPE_LABELS = {
    "created": "Создание",
    "updated": "Изменение",
    "moved": "Перемещение",
    "assigned": "Назначение",
    "returned": "Возврат",
    "maintenance": "Обслуживание",
    "retired": "Списание",
    "other": "Прочее",
}
EVENT_TYPE_OPTIONS = [{"value": k, "label": v} for k, v in EVENT_TYPE_LABELS.items()]


def is_asset_inactive(asset: Asset) -> bool:
    if not asset.last_seen_at:
        return True
    threshold = datetime.utcnow() - timedelta(days=INACTIVE_DAYS_THRESHOLD)
    return asset.last_seen_at.replace(tzinfo=None) < threshold


@router.get("/assets", name="assets_list")
async def assets_list(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_user),
    name: str | None = Query(None),
    status: AssetStatus | None = Query(None),
    asset_type: str | None = Query(None),
    location: str | None = Query(None),
):
    q = select(Asset).order_by(Asset.id)
    if name:
        q = q.where(Asset.name.ilike(f"%{name}%"))
    if status is not None:
        q = q.where(Asset.status == status)
    if asset_type:
        q = q.where(Asset.asset_type.ilike(f"%{asset_type}%"))
    if location:
        q = q.where(Asset.location.ilike(f"%{location}%"))
    result = await db.execute(q)
    assets = list(result.scalars().all())
    return templates.TemplateResponse(
        "assets_list.html",
        {
            "request": request,
            "user": current_user,
            "assets": assets,
            "filters": {"name": name, "status": status, "asset_type": asset_type, "location": location},
            "status_choices": AssetStatus,
            "status_labels": STATUS_LABELS,
            "is_inactive_fn": is_asset_inactive,
        },
    )


@router.get("/assets/export", name="assets_export")
async def assets_export(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_user),
):
    result = await db.execute(select(Asset).order_by(Asset.id))
    assets = list(result.scalars().all())
    buf = export_assets_xlsx(assets)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=assets.xlsx"},
    )


@router.get("/assets/{asset_id:int}", name="asset_detail")
async def asset_detail(
    request: Request,
    asset_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_user),
):
    result = await db.execute(
        select(Asset)
        .where(Asset.id == asset_id)
        .options(selectinload(Asset.events))
    )
    asset = result.scalar_one_or_none()
    if not asset:
        from fastapi import HTTPException
        raise HTTPException(404, "Asset not found")
    events = sorted(asset.events, key=lambda e: e.created_at or datetime.min, reverse=True)
    return templates.TemplateResponse(
        "asset_detail.html",
        {
            "request": request,
            "user": current_user,
            "asset": asset,
            "events": events,
            "is_inactive": is_asset_inactive(asset),
            "event_type_options": EVENT_TYPE_OPTIONS,
            "event_type_labels": EVENT_TYPE_LABELS,
        },
    )


@router.get("/assets/create", name="asset_create")
async def asset_create_form(
    request: Request,
    current_user: User = Depends(require_user),
):
    return templates.TemplateResponse(
        "asset_form.html",
        {
            "request": request,
            "user": current_user,
            "asset": None,
            "status_choices": AssetStatus,
            "status_labels": STATUS_LABELS,
        },
    )


@router.post("/assets/create", name="asset_create_post")
async def asset_create(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_user),
    name: str = Form(...),
    serial_number: str | None = Form(None),
    asset_type: str | None = Form(None),
    location: str | None = Form(None),
    status: AssetStatus = Form(AssetStatus.active),
    description: str | None = Form(None),
    last_seen_at: str | None = Form(None),
):
    from datetime import datetime
    asset = Asset(
        name=name,
        serial_number=serial_number if serial_number else None,
        asset_type=asset_type if asset_type else None,
        location=location if location else None,
        status=status,
        description=description if description else None,
        last_seen_at=datetime.fromisoformat(last_seen_at) if last_seen_at else None,
    )
    db.add(asset)
    await db.flush()
    # Create initial event
    event = AssetEvent(
        asset_id=asset.id,
        event_type=AssetEventType.created,
        description="Asset created",
        created_by_id=current_user.id,
    )
    db.add(event)
    await db.flush()
    return RedirectResponse(url=f"/assets/{asset.id}", status_code=302)


@router.get("/assets/{asset_id:int}/edit", name="asset_edit")
async def asset_edit_form(
    request: Request,
    asset_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_user),
):
    result = await db.execute(select(Asset).where(Asset.id == asset_id))
    asset = result.scalar_one_or_none()
    if not asset:
        from fastapi import HTTPException
        raise HTTPException(404, "Asset not found")
    return templates.TemplateResponse(
        "asset_form.html",
        {
            "request": request,
            "user": current_user,
            "asset": asset,
            "status_choices": AssetStatus,
            "status_labels": STATUS_LABELS,
        },
    )


@router.post("/assets/{asset_id:int}/edit", name="asset_edit_post")
async def asset_edit(
    asset_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_user),
    name: str = Form(...),
    serial_number: str | None = Form(None),
    asset_type: str | None = Form(None),
    location: str | None = Form(None),
    status: AssetStatus = Form(...),
    description: str | None = Form(None),
    last_seen_at: str | None = Form(None),
):
    from datetime import datetime
    result = await db.execute(select(Asset).where(Asset.id == asset_id))
    asset = result.scalar_one_or_none()
    if not asset:
        from fastapi import HTTPException
        raise HTTPException(404, "Asset not found")
    asset.name = name
    asset.serial_number = serial_number if serial_number else None
    asset.asset_type = asset_type if asset_type else None
    asset.location = location if location else None
    asset.status = status
    asset.description = description if description else None
    if last_seen_at:
        try:
            asset.last_seen_at = datetime.fromisoformat(last_seen_at)
        except ValueError:
            asset.last_seen_at = None
    else:
        asset.last_seen_at = None
    await db.flush()
    # Create update event
    event = AssetEvent(
        asset_id=asset_id,
        event_type=AssetEventType.updated,
        description="Asset updated",
        created_by_id=current_user.id,
    )
    db.add(event)
    await db.flush()
    return RedirectResponse(url=f"/assets/{asset_id}", status_code=302)


@router.post("/assets/{asset_id:int}/event", name="asset_add_event")
async def asset_add_event(
    asset_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_user),
    event_type: AssetEventType = Form(...),
    description: str | None = Form(None),
):
    result = await db.execute(select(Asset).where(Asset.id == asset_id))
    asset = result.scalar_one_or_none()
    if not asset:
        from fastapi import HTTPException
        raise HTTPException(404, "Asset not found")
    event = AssetEvent(
        asset_id=asset_id,
        event_type=event_type,
        description=description or "",
        created_by_id=current_user.id,
    )
    db.add(event)
    await db.flush()
    return RedirectResponse(url=f"/assets/{asset_id}", status_code=302)
