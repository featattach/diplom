from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Request, Query, Form, HTTPException
from fastapi.responses import RedirectResponse, StreamingResponse, FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import INACTIVE_DAYS_THRESHOLD, QR_DIR
from app.database import get_db
from app.models import Asset, AssetEvent, Company, InventoryCampaign, InventoryItem
from app.models.asset import AssetStatus, AssetEventType, EquipmentKind
from app.auth import require_user, require_role
from app.models.user import User, UserRole
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

EQUIPMENT_KIND_LABELS = {
    "desktop": "Системный блок",
    "nettop": "Неттоп",
    "laptop": "Ноутбук",
    "monitor": "Монитор",
    "mfu": "МФУ",
    "printer": "Принтер",
    "scanner": "Сканер",
    "switch": "Коммутатор",
    "server": "Сервер",
    "monoblock": "Моноблок",  # устаревший тип, для старых записей
}
EQUIPMENT_KIND_CHOICES = [{"value": k, "label": v} for k, v in EQUIPMENT_KIND_LABELS.items()]
# Типы с экраном (диагональ/разрешение) — только ноутбук и монитор; системный блок без диагонали
EQUIPMENT_KIND_HAS_SCREEN = ("laptop", "monitor")
# Типы с полем «Юниты (U)» — только сервер
EQUIPMENT_KIND_NEEDS_RACK = ("server",)
# Типы с общими тех. полями (процессор, ОЗУ, диски и т.д.)
EQUIPMENT_KIND_HAS_TECH = ("desktop", "nettop", "laptop", "server")
# Типы доп. устройств (для блока «Доп. устройства»)
EXTRA_COMPONENT_TYPES = [
    {"value": "cpu", "label": "Процессор"},
    {"value": "ram", "label": "ОЗУ"},
    {"value": "disk", "label": "Диск"},
    {"value": "network_card", "label": "Сетевая карта"},
    {"value": "other", "label": "Прочее"},
]


def is_asset_inactive(asset: Asset) -> bool:
    if not asset.last_seen_at:
        return True
    threshold = datetime.utcnow() - timedelta(days=INACTIVE_DAYS_THRESHOLD)
    return asset.last_seen_at.replace(tzinfo=None) < threshold


def _generate_qr_for_asset(asset_id: int, base_url: str) -> None:
    """Генерирует PNG QR-кода с ссылкой на карточку актива и сохраняет в data/qrcodes."""
    import qrcode
    QR_DIR.mkdir(parents=True, exist_ok=True)
    url = f"{base_url.rstrip('/')}/assets/{asset_id}"
    qr = qrcode.QRCode(version=1, box_size=8, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    path = QR_DIR / f"{asset_id}.png"
    img.save(path, "PNG")


@router.get("/assets", name="assets_list")
async def assets_list(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_user),
    name: str | None = Query(None),
    status: str | None = Query(None),
    equipment_kind: str | None = Query(None),
    location: str | None = Query(None),
    company_id: str | None = Query(None),
):
    status_filter = None
    if status and status.strip() and status.strip() in ("active", "inactive", "maintenance", "retired"):
        status_filter = AssetStatus(status.strip())
    q = select(Asset).options(selectinload(Asset.company)).order_by(Asset.id)
    if name:
        q = q.where(Asset.name.ilike(f"%{name}%"))
    if status_filter is not None:
        q = q.where(Asset.status == status_filter)
    if equipment_kind:
        q = q.where(Asset.equipment_kind == equipment_kind)
    if location and location.strip():
        q = q.where(Asset.location == location.strip())
    if company_id and company_id.strip():
        try:
            q = q.where(Asset.company_id == int(company_id.strip()))
        except ValueError:
            pass
    result = await db.execute(q)
    assets = list(result.scalars().all())
    companies_result = await db.execute(select(Company).order_by(Company.name))
    companies = list(companies_result.scalars().all())
    locations_result = await db.execute(
        select(Asset.location).where(Asset.location.isnot(None)).where(Asset.location != "").distinct().order_by(Asset.location)
    )
    location_choices = [r[0] for r in locations_result.all()]
    return templates.TemplateResponse(
        "assets_list.html",
        {
            "request": request,
            "user": current_user,
            "assets": assets,
            "companies": companies,
            "location_choices": location_choices,
            "filters": {"name": name, "status": status, "equipment_kind": equipment_kind, "location": location or "", "company_id": company_id or ""},
            "status_choices": AssetStatus,
            "status_labels": STATUS_LABELS,
            "equipment_kind_choices": EQUIPMENT_KIND_CHOICES,
            "equipment_kind_labels": EQUIPMENT_KIND_LABELS,
            "is_inactive_fn": is_asset_inactive,
        },
    )


@router.get("/assets/export", name="assets_export")
async def assets_export(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_user),
):
    result = await db.execute(select(Asset).options(selectinload(Asset.company)).order_by(Asset.id))
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
    inventory: int | None = Query(None, description="ID кампании инвентаризации для отметки «отсканировано»"),
):
    result = await db.execute(
        select(Asset)
        .where(Asset.id == asset_id)
        .options(selectinload(Asset.events), selectinload(Asset.company), selectinload(Asset.inventory_items))
    )
    asset = result.scalar_one_or_none()
    if not asset:
        raise HTTPException(404, "Asset not found")
    events = sorted(asset.events, key=lambda e: e.created_at or datetime.min, reverse=True)
    extra_components_list = _parse_extra_components(asset)
    component_type_labels = {t["value"]: t["label"] for t in EXTRA_COMPONENT_TYPES}
    qr_path = QR_DIR / f"{asset.id}.png"

    inventory_campaign = None
    inventory_item = None
    if inventory:
        camp_result = await db.execute(
            select(InventoryCampaign).where(InventoryCampaign.id == inventory)
        )
        inventory_campaign = camp_result.scalar_one_or_none()
        if inventory_campaign:
            item_result = await db.execute(
                select(InventoryItem)
                .where(InventoryItem.campaign_id == inventory)
                .where(InventoryItem.asset_id == asset_id)
            )
            inventory_item = item_result.scalar_one_or_none()

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
            "equipment_kind_labels": EQUIPMENT_KIND_LABELS,
            "extra_components_list": extra_components_list,
            "component_type_labels": component_type_labels,
            "qr_exists": qr_path.exists(),
            "inventory_campaign": inventory_campaign,
            "inventory_item": inventory_item,
        },
    )


@router.get("/assets/{asset_id:int}/qr-image", name="asset_qr_image")
async def asset_qr_image(
    asset_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_user),
):
    """Отдаёт PNG QR-кода для актива (если сгенерирован)."""
    path = QR_DIR / f"{asset_id}.png"
    if not path.is_file():
        raise HTTPException(404, "QR-код не сгенерирован")
    result = await db.execute(select(Asset).where(Asset.id == asset_id))
    if not result.scalar_one_or_none():
        raise HTTPException(404, "Asset not found")
    return FileResponse(path, media_type="image/png")


@router.post("/assets/{asset_id:int}/generate-qr", name="asset_generate_qr")
async def asset_generate_qr(
    request: Request,
    asset_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_user),
):
    """Генерирует или перезаписывает QR-код для актива, редирект на карточку."""
    result = await db.execute(select(Asset).where(Asset.id == asset_id))
    asset = result.scalar_one_or_none()
    if not asset:
        raise HTTPException(404, "Asset not found")
    base_url = str(request.base_url).rstrip("/")
    _generate_qr_for_asset(asset_id, base_url)
    return RedirectResponse(
        request.url_for("asset_detail", asset_id=asset_id),
        status_code=303,
    )


@router.post("/assets/{asset_id:int}/mark-inventory-found", name="asset_mark_inventory_found")
async def asset_mark_inventory_found(
    request: Request,
    asset_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_user),
    campaign_id: int = Form(...),
):
    """Отмечает оборудование как отсканированное (найденное) в рамках кампании инвентаризации."""
    result = await db.execute(select(Asset).where(Asset.id == asset_id))
    if not result.scalar_one_or_none():
        raise HTTPException(404, "Asset not found")
    camp_result = await db.execute(
        select(InventoryCampaign).where(InventoryCampaign.id == campaign_id)
    )
    if not camp_result.scalar_one_or_none():
        raise HTTPException(404, "Campaign not found")
    item_result = await db.execute(
        select(InventoryItem)
        .where(InventoryItem.campaign_id == campaign_id)
        .where(InventoryItem.asset_id == asset_id)
    )
    item = item_result.scalar_one_or_none()
    if not item:
        item = InventoryItem(
            campaign_id=campaign_id,
            asset_id=asset_id,
            found=True,
            found_at=datetime.utcnow(),
        )
        db.add(item)
    else:
        item.found = True
        item.found_at = datetime.utcnow()
    await db.flush()
    return RedirectResponse(
        request.url_for("asset_detail", asset_id=asset_id) + f"?inventory={campaign_id}&marked=1",
        status_code=303,
    )


@router.get("/assets/create", name="asset_create")
async def asset_create_form(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin, UserRole.user)),
):
    companies_result = await db.execute(select(Company).order_by(Company.name))
    companies = list(companies_result.scalars().all())
    return templates.TemplateResponse(
        "asset_form.html",
        {
            "request": request,
            "user": current_user,
            "asset": None,
            "companies": companies,
            "status_choices": AssetStatus,
            "status_labels": STATUS_LABELS,
            "equipment_kind_choices": EQUIPMENT_KIND_CHOICES,
            "equipment_kind_has_screen": EQUIPMENT_KIND_HAS_SCREEN,
            "equipment_kind_needs_rack": EQUIPMENT_KIND_NEEDS_RACK,
            "equipment_kind_has_tech": EQUIPMENT_KIND_HAS_TECH,
            "extra_component_types": EXTRA_COMPONENT_TYPES,
            "extra_components_list": [],
        },
    )


def _parse_asset_form(
    name, serial_number, asset_type, equipment_kind, model, location, status, description, last_seen_at,
    cpu, ram, disk1_type, disk1_capacity, network_card, motherboard,
    screen_diagonal, screen_resolution, power_supply, monitor_diagonal,
    rack_units=None, extra_components_json=None, company_id=None,
):
    import json
    from datetime import datetime
    data = {
        "name": name,
        "serial_number": serial_number or None,
        "asset_type": asset_type or None,
        "equipment_kind": equipment_kind or None,
        "model": model or None,
        "location": location or None,
        "status": status,
        "description": description or None,
        "last_seen_at": datetime.fromisoformat(last_seen_at) if last_seen_at else None,
        "cpu": cpu or None,
        "ram": ram or None,
        "disk1_type": disk1_type or None,
        "disk1_capacity": disk1_capacity or None,
        "network_card": network_card or None,
        "motherboard": motherboard or None,
        "screen_diagonal": screen_diagonal or None,
        "screen_resolution": screen_resolution or None,
        "power_supply": power_supply or None,
        "monitor_diagonal": monitor_diagonal or None,
        "rack_units": int(rack_units) if rack_units not in (None, "") else None,
        "company_id": int(company_id) if company_id not in (None, "") else None,
    }
    if extra_components_json:
        try:
            data["extra_components"] = json.dumps(json.loads(extra_components_json), ensure_ascii=False)
        except (json.JSONDecodeError, TypeError):
            data["extra_components"] = None
    else:
        data["extra_components"] = None
    return data


def _parse_extra_components(asset):
    import json
    if not getattr(asset, "extra_components", None):
        return []
    try:
        return json.loads(asset.extra_components)
    except (json.JSONDecodeError, TypeError):
        return []


@router.post("/assets/create", name="asset_create_post")
async def asset_create(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin, UserRole.user)),
    name: str = Form(...),
    serial_number: str | None = Form(None),
    asset_type: str | None = Form(None),
    equipment_kind: str | None = Form(None),
    model: str | None = Form(None),
    location: str | None = Form(None),
    status: AssetStatus = Form(AssetStatus.active),
    description: str | None = Form(None),
    last_seen_at: str | None = Form(None),
    cpu: str | None = Form(None),
    ram: str | None = Form(None),
    disk1_type: str | None = Form(None),
    disk1_capacity: str | None = Form(None),
    network_card: str | None = Form(None),
    motherboard: str | None = Form(None),
    screen_diagonal: str | None = Form(None),
    screen_resolution: str | None = Form(None),
    power_supply: str | None = Form(None),
    monitor_diagonal: str | None = Form(None),
    rack_units: str | None = Form(None),
    extra_components: str | None = Form(None),
    company_id: str | None = Form(None),
):
    data = _parse_asset_form(
        name, serial_number, asset_type, equipment_kind, model, location, status, description, last_seen_at,
        cpu, ram, disk1_type, disk1_capacity, network_card, motherboard,
        screen_diagonal, screen_resolution, power_supply, monitor_diagonal,
        rack_units=rack_units, extra_components_json=extra_components, company_id=company_id,
    )
    asset = Asset(**data)
    db.add(asset)
    await db.flush()
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
    current_user: User = Depends(require_role(UserRole.admin, UserRole.user)),
):
    result = await db.execute(select(Asset).where(Asset.id == asset_id))
    asset = result.scalar_one_or_none()
    if not asset:
        from fastapi import HTTPException
        raise HTTPException(404, "Asset not found")
    companies_result = await db.execute(select(Company).order_by(Company.name))
    companies = list(companies_result.scalars().all())
    return templates.TemplateResponse(
        "asset_form.html",
        {
            "request": request,
            "user": current_user,
            "asset": asset,
            "companies": companies,
            "status_choices": AssetStatus,
            "status_labels": STATUS_LABELS,
            "equipment_kind_choices": EQUIPMENT_KIND_CHOICES,
            "equipment_kind_has_screen": EQUIPMENT_KIND_HAS_SCREEN,
            "equipment_kind_needs_rack": EQUIPMENT_KIND_NEEDS_RACK,
            "equipment_kind_has_tech": EQUIPMENT_KIND_HAS_TECH,
            "extra_component_types": EXTRA_COMPONENT_TYPES,
            "extra_components_list": _parse_extra_components(asset),
        },
    )


@router.post("/assets/{asset_id:int}/edit", name="asset_edit_post")
async def asset_edit(
    asset_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin, UserRole.user)),
    name: str = Form(...),
    serial_number: str | None = Form(None),
    asset_type: str | None = Form(None),
    equipment_kind: str | None = Form(None),
    model: str | None = Form(None),
    location: str | None = Form(None),
    status: AssetStatus = Form(...),
    description: str | None = Form(None),
    last_seen_at: str | None = Form(None),
    cpu: str | None = Form(None),
    ram: str | None = Form(None),
    disk1_type: str | None = Form(None),
    disk1_capacity: str | None = Form(None),
    network_card: str | None = Form(None),
    motherboard: str | None = Form(None),
    screen_diagonal: str | None = Form(None),
    screen_resolution: str | None = Form(None),
    power_supply: str | None = Form(None),
    monitor_diagonal: str | None = Form(None),
    rack_units: str | None = Form(None),
    extra_components: str | None = Form(None),
    company_id: str | None = Form(None),
):
    result = await db.execute(select(Asset).where(Asset.id == asset_id))
    asset = result.scalar_one_or_none()
    if not asset:
        from fastapi import HTTPException
        raise HTTPException(404, "Asset not found")
    data = _parse_asset_form(
        name, serial_number, asset_type, equipment_kind, model, location, status, description, last_seen_at,
        cpu, ram, disk1_type, disk1_capacity, network_card, motherboard,
        screen_diagonal, screen_resolution, power_supply, monitor_diagonal,
        rack_units=rack_units, extra_components_json=extra_components, company_id=company_id,
    )
    for key, value in data.items():
        setattr(asset, key, value)
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
    current_user: User = Depends(require_role(UserRole.admin, UserRole.user)),
    event_type: AssetEventType = Form(...),
    description: str | None = Form(None),
):
    result = await db.execute(select(Asset).where(Asset.id == asset_id))
    asset = result.scalar_one_or_none()
    if not asset:
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


@router.get("/scan", name="scan_qr")
async def scan_qr_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_user),
):
    """Страница сканирования QR-кода камерой (для перехода на карточку и отметки «отсканировано»)."""
    campaigns_result = await db.execute(
        select(InventoryCampaign)
        .where(InventoryCampaign.finished_at.is_(None))
        .order_by(InventoryCampaign.started_at.desc())
    )
    campaigns = list(campaigns_result.scalars().all())
    return templates.TemplateResponse(
        "scan.html",
        {"request": request, "user": current_user, "campaigns": campaigns},
    )
