"""
CRUD техники: список, создание, редактирование, карточка актива, импорт и экспорт Excel.
"""
from fastapi import APIRouter, Depends, Request, Query, Form, File, UploadFile, HTTPException
from fastapi.responses import RedirectResponse, StreamingResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import INACTIVE_DAYS_THRESHOLD, MAX_IMPORT_SIZE_MB
from app.repositories import asset_repo, reference_repo, inventory_repo
from app.services.attachments_service import get_qr_path
from app.utils.asset_helpers import is_asset_inactive
from app.constants import (
    ASSET_FIELD_LABELS,
    EQUIPMENT_KIND_CHOICES,
    EQUIPMENT_KIND_HAS_MANUFACTURE_DATE,
    EQUIPMENT_KIND_HAS_OS,
    EQUIPMENT_KIND_HAS_SCREEN,
    EQUIPMENT_KIND_HAS_TECH,
    EQUIPMENT_KIND_LABELS,
    EQUIPMENT_KIND_NEEDS_RACK,
    EVENT_TYPE_LABELS,
    EVENT_TYPE_OPTIONS,
    EXTRA_COMPONENT_TYPES,
    OS_OPTIONS,
    STATUS_LABELS,
)
from app.database import get_db
from app.models import Asset
from app.models.asset import AssetStatus, EquipmentKind
from app.auth import require_user, require_role
from app.models.user import User, UserRole
from app.templates_ctx import templates
from app.services.assets_service import create_asset as service_create_asset, update_asset as service_update_asset
from app.services.export_xlsx import export_assets_xlsx
from app.services.import_xlsx import parse_import_xlsx, build_import_template_xlsx

router = APIRouter(prefix="", tags=["assets"])


@router.get("/assets", name="assets_list", include_in_schema=False)
async def assets_list(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_user),
    name: str | None = Query(None),
    status: str | None = Query(None),
    inactive_by_activity: bool = Query(False, description="Неактивные по последней активности (как на дашборде)"),
    equipment_kind: str | None = Query(None),
    location: str | None = Query(None),
    company_id: str | None = Query(None),
    sort: str | None = Query("newest", description="Сортировка по дате добавления: newest / oldest"),
):
    assets = await asset_repo.get_assets_list(
        db, name=name, status=status, inactive_by_activity=inactive_by_activity,
        equipment_kind=equipment_kind, location=location, company_id=company_id, sort=sort,
    )
    if inactive_by_activity:
        assets = [a for a in assets if is_asset_inactive(a)]
    companies = await reference_repo.get_companies_ordered(db)
    location_choices = await asset_repo.get_distinct_locations(db)
    sort_val = "newest" if sort not in ("newest", "oldest") else sort
    qp = {
        k: v
        for k, v in [
            ("name", name),
            ("status", status),
            ("inactive_by_activity", "1" if inactive_by_activity else None),
            ("equipment_kind", equipment_kind),
            ("location", location or ""),
            ("company_id", company_id or ""),
            ("sort", sort_val if sort_val != "newest" else None),
        ]
        if v is not None and v != ""
    }
    base_export_url = request.url_for("assets_export")
    export_url = str(base_export_url.include_query_params(**qp)) if qp else str(base_export_url)
    return templates.TemplateResponse(
        "assets_list.html",
        {
            "request": request,
            "user": current_user,
            "assets": assets,
            "companies": companies,
            "location_choices": location_choices,
            "export_url": export_url,
            "filters": {"name": name, "status": status, "inactive_by_activity": inactive_by_activity, "equipment_kind": equipment_kind, "location": location or "", "company_id": company_id or "", "sort": sort_val},
            "status_choices": AssetStatus,
            "status_labels": STATUS_LABELS,
            "equipment_kind_choices": EQUIPMENT_KIND_CHOICES,
            "equipment_kind_labels": EQUIPMENT_KIND_LABELS,
            "is_inactive_fn": is_asset_inactive,
            "inactive_days_threshold": INACTIVE_DAYS_THRESHOLD,
        },
    )


@router.get("/assets/export", name="assets_export", include_in_schema=False)
async def assets_export(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_user),
    name: str | None = Query(None),
    status: str | None = Query(None),
    inactive_by_activity: bool = Query(False),
    equipment_kind: str | None = Query(None),
    location: str | None = Query(None),
    company_id: str | None = Query(None),
    sort: str | None = Query("newest"),
):
    sort_val = "newest" if sort not in ("newest", "oldest") else sort
    assets = await asset_repo.get_assets_list(
        db, name=name, status=status, inactive_by_activity=inactive_by_activity,
        equipment_kind=equipment_kind, location=location, company_id=company_id, sort=sort_val,
    )
    if inactive_by_activity:
        assets = [a for a in assets if is_asset_inactive(a)]
    buf = export_assets_xlsx(assets)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=assets.xlsx"},
    )


@router.get("/assets/import", name="assets_import", include_in_schema=False)
async def assets_import_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin, UserRole.user)),
    imported: int | None = Query(None),
    errors: str | None = Query(None),
):
    return templates.TemplateResponse(
        "assets_import.html",
        {
            "request": request,
            "user": current_user,
            "imported_count": imported,
            "import_errors": errors or "",
            "status_options": list(STATUS_LABELS.values()),
            "equipment_kind_options": [c["label"] for c in EQUIPMENT_KIND_CHOICES],
        },
    )


@router.get("/assets/import/template", name="assets_import_template", include_in_schema=False)
async def assets_import_template_download(
    current_user: User = Depends(require_role(UserRole.admin, UserRole.user)),
):
    buf = build_import_template_xlsx()
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=import_oborudovanie_shablon.xlsx"},
    )


@router.post("/assets/import", name="assets_import_post", include_in_schema=False)
async def assets_import_upload(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin, UserRole.user)),
    file: UploadFile = File(...),
):
    base = request.url_for("assets_import")
    if not file.filename or not file.filename.lower().endswith(".xlsx"):
        return RedirectResponse(
            str(base.include_query_params(errors="Выберите файл Excel")),
            status_code=302,
        )
    content = await file.read()
    if len(content) > MAX_IMPORT_SIZE_MB * 1024 * 1024:
        return RedirectResponse(
            str(base.include_query_params(errors=f"Файл слишком большой (макс. {MAX_IMPORT_SIZE_MB} МБ)")),
            status_code=302,
        )
    rows, parse_errors = parse_import_xlsx(content)
    if parse_errors:
        err_str = "; ".join(parse_errors[:5])
        if len(parse_errors) > 5:
            err_str += f" (всего {len(parse_errors)})"
        return RedirectResponse(
            str(base.include_query_params(errors=err_str)),
            status_code=302,
        )
    if not rows:
        return RedirectResponse(
            str(base.include_query_params(errors="Нет строк для импорта (обязателен столбец Название)")),
            status_code=302,
        )
    existing_serials = await asset_repo.get_existing_serial_numbers(db)
    seen_serials_in_batch = set()
    imported = 0
    skip_messages = []
    for idx, r in enumerate(rows, start=2):
        serial = (r.get("serial_number") or "").strip()
        if serial:
            if serial in existing_serials:
                skip_messages.append(f"Строка {idx}: серийный номер «{serial}» уже есть в базе")
                continue
            if serial in seen_serials_in_batch:
                skip_messages.append(f"Строка {idx}: серийный номер «{serial}» повторяется в файле")
                continue
        try:
            company_id = None
            if r.get("company_name"):
                company = await reference_repo.find_company_by_name(db, r["company_name"].strip())
                if company:
                    company_id = company.id
            equipment_kind_val = r.get("equipment_kind")
            equipment_kind_enum = None
            if equipment_kind_val:
                try:
                    equipment_kind_enum = EquipmentKind(equipment_kind_val)
                except ValueError:
                    pass
            data = {
                "name": r["name"],
                "model": r.get("model"),
                "equipment_kind": equipment_kind_enum,
                "serial_number": serial or None,
                "location": r.get("location") or None,
                "status": r["status"],
                "asset_type": r.get("asset_type"),
                "description": r.get("description"),
                "company_id": company_id,
                "current_user": r.get("current_user"),
            }
            await service_create_asset(db, data, current_user.id, event_description="Импорт из Excel")
            imported += 1
            if serial:
                existing_serials.add(serial)
                seen_serials_in_batch.add(serial)
        except IntegrityError as e:
            await db.rollback()
            msg = "Серийный номер уже существует в базе" if "serial_number" in str(e.orig) else str(e.orig)
            return RedirectResponse(
                str(base.include_query_params(errors=f"Строка {idx}: {msg}")),
                status_code=302,
            )
    if skip_messages:
        err_param = "; ".join(skip_messages[:5])
        if len(skip_messages) > 5:
            err_param += f" (пропущено {len(skip_messages)} строк)"
        return RedirectResponse(
            str(request.url_for("assets_import").include_query_params(imported=imported, errors=err_param)),
            status_code=302,
        )
    return RedirectResponse(
        str(request.url_for("assets_import").include_query_params(imported=imported)),
        status_code=302,
    )


@router.get("/assets/{asset_id:int}", name="asset_detail", include_in_schema=False)
async def asset_detail(
    request: Request,
    asset_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_user),
    inventory: int | None = Query(None, description="ID кампании инвентаризации для отметки «отсканировано»"),
):
    asset = await asset_repo.get_asset_by_id_with_relations(db, asset_id)
    if not asset:
        raise HTTPException(404, "Asset not found")
    events = sorted(asset.events, key=lambda e: e.created_at or datetime.min, reverse=True)
    import json as _json
    for e in events:
        e.changes_list = []
        if getattr(e, "changes_json", None):
            try:
                e.changes_list = _json.loads(e.changes_json)
            except (TypeError, ValueError, _json.JSONDecodeError):
                pass
    extra_components_list = _parse_extra_components(asset)
    component_type_labels = {t["value"]: t["label"] for t in EXTRA_COMPONENT_TYPES}
    qr_path = get_qr_path(asset.id)
    network_interfaces_list = _parse_network_interfaces(asset)
    os_labels = {o["value"]: o["label"] for o in OS_OPTIONS}

    inventory_campaign = None
    inventory_item = None
    if inventory:
        inventory_campaign = await inventory_repo.get_campaign_by_id(db, inventory)
        if inventory_campaign:
            inventory_item = await inventory_repo.get_inventory_item(db, inventory, asset_id)

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
            "network_interfaces_list": network_interfaces_list,
            "os_options": OS_OPTIONS,
            "equipment_kind_has_os": EQUIPMENT_KIND_HAS_OS,
            "os_labels": os_labels,
        },
    )


def _parse_asset_form(
    name, serial_number, asset_type, equipment_kind, model, location, status, description, last_seen_at,
    cpu, ram, disk1_type, disk1_capacity, network_card, motherboard,
    screen_diagonal, screen_resolution, power_supply, monitor_diagonal,
    rack_units=None, extra_components_json=None, company_id=None,
    os=None, network_interfaces_json=None, current_user=None,
    manufacture_date=None,
):
    import json
    from datetime import date
    equipment_kind_enum = None
    if equipment_kind and equipment_kind.strip():
        try:
            equipment_kind_enum = EquipmentKind(equipment_kind.strip())
        except ValueError:
            pass
    data = {
        "name": name,
        "serial_number": serial_number or None,
        "asset_type": asset_type or None,
        "equipment_kind": equipment_kind_enum,
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
        "os": (os or "").strip() or None,
        "current_user": (current_user or "").strip() or None,
        "manufacture_date": None,
    }
    if manufacture_date and str(manufacture_date).strip():
        try:
            data["manufacture_date"] = date.fromisoformat(str(manufacture_date).strip()[:10])
        except (ValueError, TypeError):
            pass
    if extra_components_json:
        try:
            data["extra_components"] = json.dumps(json.loads(extra_components_json), ensure_ascii=False)
        except (json.JSONDecodeError, TypeError):
            data["extra_components"] = None
    else:
        data["extra_components"] = None
    if network_interfaces_json:
        try:
            data["network_interfaces"] = json.dumps(json.loads(network_interfaces_json), ensure_ascii=False)
        except (json.JSONDecodeError, TypeError):
            data["network_interfaces"] = None
    else:
        data["network_interfaces"] = None
    return data


def _parse_extra_components(asset):
    import json
    if not getattr(asset, "extra_components", None):
        return []
    try:
        return json.loads(asset.extra_components)
    except (json.JSONDecodeError, TypeError):
        return []


def _format_event_value(val) -> str:
    if val is None:
        return "—"
    if hasattr(val, "value"):
        return str(val.value)
    if hasattr(val, "isoformat"):
        return val.isoformat()[:19].replace("T", " ")
    return str(val)


def _format_network_interfaces_for_changes(json_str) -> str:
    import json
    if not json_str:
        return "—"
    try:
        arr = json.loads(json_str)
        if not isinstance(arr, list) or not arr:
            return "—"
        parts = []
        for x in arr:
            label = str(x.get("label") or "Интерфейс").strip()
            ip = str(x.get("ip") or "").strip()
            kind = str(x.get("type") or "network")
            if kind == "oob":
                parts.append(f"OOB: {ip}" if ip else "OOB")
            else:
                parts.append(f"{label}: {ip}" if ip else label)
        return "; ".join(parts)
    except (TypeError, json.JSONDecodeError):
        return "—"


def _format_extra_components_for_changes(json_str) -> str:
    import json
    if not json_str:
        return "—"
    try:
        arr = json.loads(json_str)
        if not isinstance(arr, list) or not arr:
            return "—"
        type_labels = {t["value"]: t["label"] for t in EXTRA_COMPONENT_TYPES}
        parts = []
        for x in arr:
            t = x.get("type") or "other"
            name = (x.get("name") or "").strip()
            lbl = type_labels.get(t, t)
            parts.append(f"{lbl}: {name}" if name else lbl)
        return "; ".join(parts)
    except (TypeError, json.JSONDecodeError):
        return "—"


def _build_asset_changes(asset: Asset, data: dict) -> list[dict]:
    import json
    changes = []
    for key, new_val in data.items():
        if key == "extra_components":
            old_raw = getattr(asset, key, None)
            old_str = _format_extra_components_for_changes(old_raw)
            new_str = _format_extra_components_for_changes(new_val)
            if old_str != new_str:
                changes.append({"field_label": ASSET_FIELD_LABELS.get(key, key), "old": old_str, "new": new_str})
            continue
        if key == "network_interfaces":
            old_raw = getattr(asset, key, None)
            old_str = _format_network_interfaces_for_changes(old_raw)
            new_str = _format_network_interfaces_for_changes(new_val)
            if old_str != new_str:
                changes.append({"field_label": ASSET_FIELD_LABELS.get(key, key), "old": old_str, "new": new_str})
            continue
        old_val = getattr(asset, key, None)
        if old_val == new_val:
            continue
        old_str = _format_event_value(old_val)
        new_str = _format_event_value(new_val)
        if old_str == new_str:
            continue
        changes.append({"field_label": ASSET_FIELD_LABELS.get(key, key), "old": old_str, "new": new_str})
    return changes


def _parse_network_interfaces(asset) -> list[dict]:
    import json
    if not getattr(asset, "network_interfaces", None):
        return []
    try:
        raw = json.loads(asset.network_interfaces)
        if not isinstance(raw, list):
            return []
        return [
            {"label": str(x.get("label") or "—"), "type": str(x.get("type") or "network"), "ip": str(x.get("ip") or "")}
            for x in raw
        ]
    except (json.JSONDecodeError, TypeError):
        return []


@router.get("/assets/create", name="asset_create", include_in_schema=False)
async def asset_create_form(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin, UserRole.user)),
):
    companies = await reference_repo.get_companies_ordered(db)
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
            "equipment_kind_has_os": EQUIPMENT_KIND_HAS_OS,
            "equipment_kind_has_manufacture_date": EQUIPMENT_KIND_HAS_MANUFACTURE_DATE,
            "extra_component_types": EXTRA_COMPONENT_TYPES,
            "extra_components_list": [],
            "os_options": OS_OPTIONS,
            "network_interfaces_list": [],
        },
    )


@router.post("/assets/create", name="asset_create_post", include_in_schema=False)
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
    os: str | None = Form(None),
    network_interfaces: str | None = Form(None),
    assigned_user: str | None = Form(None),
    manufacture_date: str | None = Form(None),
):
    data = _parse_asset_form(
        name, serial_number, asset_type, equipment_kind, model, location, status, description, last_seen_at,
        cpu, ram, disk1_type, disk1_capacity, network_card, motherboard,
        screen_diagonal, screen_resolution, power_supply, monitor_diagonal,
        rack_units=rack_units, extra_components_json=extra_components, company_id=company_id,
        os=os, network_interfaces_json=network_interfaces, current_user=assigned_user,
        manufacture_date=manufacture_date,
    )
    asset = await service_create_asset(db, data, current_user.id)
    return RedirectResponse(url=f"/assets/{asset.id}", status_code=302)


@router.get("/assets/{asset_id:int}/edit", name="asset_edit", include_in_schema=False)
async def asset_edit_form(
    request: Request,
    asset_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin, UserRole.user)),
):
    asset = await asset_repo.get_asset_by_id(db, asset_id)
    if not asset:
        raise HTTPException(404, "Asset not found")
    companies = await reference_repo.get_companies_ordered(db)
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
            "equipment_kind_has_os": EQUIPMENT_KIND_HAS_OS,
            "equipment_kind_has_manufacture_date": EQUIPMENT_KIND_HAS_MANUFACTURE_DATE,
            "extra_component_types": EXTRA_COMPONENT_TYPES,
            "extra_components_list": _parse_extra_components(asset),
            "os_options": OS_OPTIONS,
            "network_interfaces_list": _parse_network_interfaces(asset),
        },
    )


@router.post("/assets/{asset_id:int}/edit", name="asset_edit_post", include_in_schema=False)
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
    os: str | None = Form(None),
    network_interfaces: str | None = Form(None),
    assigned_user: str | None = Form(None),
    manufacture_date: str | None = Form(None),
):
    asset = await asset_repo.get_asset_by_id(db, asset_id)
    if not asset:
        raise HTTPException(404, "Asset not found")
    data = _parse_asset_form(
        name, serial_number, asset_type, equipment_kind, model, location, status, description, last_seen_at,
        cpu, ram, disk1_type, disk1_capacity, network_card, motherboard,
        screen_diagonal, screen_resolution, power_supply, monitor_diagonal,
        rack_units=rack_units, extra_components_json=extra_components, company_id=company_id,
        os=os, network_interfaces_json=network_interfaces, current_user=assigned_user,
        manufacture_date=manufacture_date,
    )
    changes = _build_asset_changes(asset, data)
    try:
        await service_update_asset(db, asset, data, changes, current_user.id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return RedirectResponse(url=f"/assets/{asset_id}", status_code=302)
