from datetime import datetime, timedelta
from urllib.parse import urlencode
from fastapi import APIRouter, Depends, Request, Query, Form, File, UploadFile, HTTPException
from fastapi.responses import RedirectResponse, StreamingResponse, FileResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
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
from app.services.import_xlsx import parse_import_xlsx, build_import_template_xlsx

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
    "sip_phone": "SIP-телефон",
    "monoblock": "Моноблок",  # устаревший тип, для старых записей
}
EQUIPMENT_KIND_CHOICES = [{"value": k, "label": v} for k, v in EQUIPMENT_KIND_LABELS.items()]
# Типы с экраном (диагональ/разрешение) — только ноутбук и монитор; системный блок без диагонали
EQUIPMENT_KIND_HAS_SCREEN = ("laptop", "monitor")
# Типы с полем «Юниты (U)» — только сервер
EQUIPMENT_KIND_NEEDS_RACK = ("server",)
# Типы с общими тех. полями (процессор, ОЗУ, диски и т.д.)
EQUIPMENT_KIND_HAS_TECH = ("desktop", "nettop", "laptop", "server")
# Типы с выбором ОС (ПК, ноутбук, сервер, неттоп)
EQUIPMENT_KIND_HAS_OS = ("desktop", "nettop", "laptop", "server")
# Типы с полем «Дата выпуска» (для отчёта «Светофор»)
EQUIPMENT_KIND_HAS_MANUFACTURE_DATE = ("desktop", "nettop", "laptop", "server")
# Варианты ОС
OS_OPTIONS = [
    {"value": "linux", "label": "Linux"},
    {"value": "windows_7", "label": "Windows 7"},
    {"value": "windows_10", "label": "Windows 10"},
    {"value": "windows_11", "label": "Windows 11"},
]
# Подписи полей для журнала «было → стало»
ASSET_FIELD_LABELS = {
    "name": "Название",
    "serial_number": "Серийный номер",
    "asset_type": "Категория",
    "equipment_kind": "Тип техники",
    "model": "Модель",
    "location": "Расположение",
    "status": "Статус",
    "description": "Описание",
    "last_seen_at": "Последняя активность",
    "cpu": "Процессор",
    "ram": "ОЗУ",
    "disk1_type": "Тип диска",
    "disk1_capacity": "Объём диска",
    "network_card": "Сетевая карта",
    "motherboard": "Материнская плата",
    "screen_diagonal": "Диагональ экрана",
    "screen_resolution": "Разрешение экрана",
    "power_supply": "Блок питания",
    "monitor_diagonal": "Монитор (диагональ)",
    "rack_units": "Юниты (U)",
    "company_id": "Организация",
    "os": "ОС",
    "network_interfaces": "Сетевые интерфейсы",
    "current_user": "Пользователь (кто использует)",
    "manufacture_date": "Дата выпуска",
}
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
    inactive_by_activity: bool = Query(False, description="Неактивные по последней активности (как на дашборде)"),
    equipment_kind: str | None = Query(None),
    location: str | None = Query(None),
    company_id: str | None = Query(None),
    sort: str | None = Query("newest", description="Сортировка по дате добавления: newest / oldest"),
):
    q = _assets_list_query(name, status, inactive_by_activity, equipment_kind, location, company_id, sort)
    result = await db.execute(q)
    assets = list(result.scalars().all())
    if inactive_by_activity:
        assets = [a for a in assets if is_asset_inactive(a)]
    companies_result = await db.execute(select(Company).order_by(Company.name))
    companies = list(companies_result.scalars().all())
    locations_result = await db.execute(
        select(Asset.location).where(Asset.location.isnot(None)).where(Asset.location != "").distinct().order_by(Asset.location)
    )
    location_choices = [r[0] for r in locations_result.all()]
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


def _assets_list_query(
    name: str | None,
    status: str | None,
    inactive_by_activity: bool,
    equipment_kind: str | None,
    location: str | None,
    company_id: str | None,
    sort: str = "newest",
):
    """Общая логика фильтрации списка активов (для списка и экспорта)."""
    status_filter = None
    if status and status.strip() and status.strip() in ("active", "inactive", "maintenance", "retired"):
        status_filter = AssetStatus(status.strip())
    q = select(Asset).options(selectinload(Asset.company))
    if sort == "oldest":
        q = q.order_by(Asset.created_at.asc(), Asset.id.asc())
    else:
        q = q.order_by(Asset.created_at.desc(), Asset.id.desc())
    if name:
        q = q.where(Asset.name.ilike(f"%{name}%"))
    if inactive_by_activity:
        q = q.where(Asset.status != AssetStatus.retired)
    elif status_filter is not None:
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
    return q


@router.get("/assets/export", name="assets_export")
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
    q = _assets_list_query(name, status, inactive_by_activity, equipment_kind, location, company_id, sort_val)
    result = await db.execute(q)
    assets = list(result.scalars().all())
    if inactive_by_activity:
        assets = [a for a in assets if is_asset_inactive(a)]
    buf = export_assets_xlsx(assets)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=assets.xlsx"},
    )


@router.get("/assets/import", name="assets_import")
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


@router.get("/assets/import/template", name="assets_import_template")
async def assets_import_template_download(
    current_user: User = Depends(require_role(UserRole.admin, UserRole.user)),
):
    buf = build_import_template_xlsx()
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=import_oborudovanie_shablon.xlsx"},
    )


@router.post("/assets/import", name="assets_import_post")
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
    # Серийные номера уже в БД (для проверки дубликатов)
    existing = await db.execute(select(Asset.serial_number).where(Asset.serial_number.isnot(None)).where(Asset.serial_number != ""))
    existing_serials = {row[0] for row in existing.all()}
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
                comp = await db.execute(
                    select(Company).where(Company.name.ilike(r["company_name"].strip()))
                )
                company = comp.scalar_one_or_none()
                if company:
                    company_id = company.id
            data = {
                "name": r["name"],
                "model": r.get("model"),
                "equipment_kind": r.get("equipment_kind"),
                "serial_number": serial or None,
                "location": r.get("location") or None,
                "status": r["status"],
                "asset_type": r.get("asset_type"),
                "description": r.get("description"),
                "company_id": company_id,
                "current_user": r.get("current_user"),
            }
            asset = Asset(**data)
            db.add(asset)
            await db.flush()
            ev = AssetEvent(
                asset_id=asset.id,
                event_type=AssetEventType.created,
                description="Импорт из Excel",
                created_by_id=current_user.id,
            )
            db.add(ev)
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
    qr_path = QR_DIR / f"{asset.id}.png"
    network_interfaces_list = _parse_network_interfaces(asset)
    os_labels = {o["value"]: o["label"] for o in OS_OPTIONS}

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
            "network_interfaces_list": network_interfaces_list,
            "os_options": OS_OPTIONS,
            "equipment_kind_has_os": EQUIPMENT_KIND_HAS_OS,
            "os_labels": os_labels,
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
            "equipment_kind_has_os": EQUIPMENT_KIND_HAS_OS,
            "equipment_kind_has_manufacture_date": EQUIPMENT_KIND_HAS_MANUFACTURE_DATE,
            "extra_component_types": EXTRA_COMPONENT_TYPES,
            "extra_components_list": [],
            "os_options": OS_OPTIONS,
            "network_interfaces_list": [],
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
    from datetime import datetime, date
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
    """Форматирует значение для отображения в журнале «было → стало»."""
    if val is None:
        return "—"
    if hasattr(val, "value"):  # enum
        return str(val.value)
    if hasattr(val, "isoformat"):
        return val.isoformat()[:19].replace("T", " ")
    return str(val)


def _format_network_interfaces_for_changes(json_str) -> str:
    """Читаемое представление сетевых интерфейсов без сырого JSON (label, type, ip)."""
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
    """Читаемое представление доп. устройств без сырого JSON."""
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
    """Сравнивает текущее состояние актива с новыми данными, возвращает список изменений."""
    import json
    changes = []
    for key, new_val in data.items():
        if key == "extra_components":
            old_raw = getattr(asset, key, None)
            old_str = _format_extra_components_for_changes(old_raw)
            new_str = _format_extra_components_for_changes(new_val)
            if old_str != new_str:
                changes.append({
                    "field_label": ASSET_FIELD_LABELS.get(key, key),
                    "old": old_str,
                    "new": new_str,
                })
            continue
        if key == "network_interfaces":
            old_raw = getattr(asset, key, None)
            old_str = _format_network_interfaces_for_changes(old_raw)
            new_str = _format_network_interfaces_for_changes(new_val)
            if old_str != new_str:
                changes.append({
                    "field_label": ASSET_FIELD_LABELS.get(key, key),
                    "old": old_str,
                    "new": new_str,
                })
            continue
        old_val = getattr(asset, key, None)
        if old_val == new_val:
            continue
        old_str = _format_event_value(old_val)
        new_str = _format_event_value(new_val)
        if old_str == new_str:
            continue
        changes.append({
            "field_label": ASSET_FIELD_LABELS.get(key, key),
            "old": old_str,
            "new": new_str,
        })
    return changes


def _parse_network_interfaces(asset) -> list[dict]:
    """Возвращает список {label, type, ip} из asset.network_interfaces JSON."""
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
            "equipment_kind_has_os": EQUIPMENT_KIND_HAS_OS,
            "equipment_kind_has_manufacture_date": EQUIPMENT_KIND_HAS_MANUFACTURE_DATE,
            "extra_component_types": EXTRA_COMPONENT_TYPES,
            "extra_components_list": _parse_extra_components(asset),
            "os_options": OS_OPTIONS,
            "network_interfaces_list": _parse_network_interfaces(asset),
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
    os: str | None = Form(None),
    network_interfaces: str | None = Form(None),
    assigned_user: str | None = Form(None),
    manufacture_date: str | None = Form(None),
):
    result = await db.execute(select(Asset).where(Asset.id == asset_id))
    asset = result.scalar_one_or_none()
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
    for key, value in data.items():
        setattr(asset, key, value)
    await db.flush()
    import json
    event = AssetEvent(
        asset_id=asset_id,
        event_type=AssetEventType.updated,
        description="Изменение карточки" if changes else "Asset updated",
        created_by_id=current_user.id,
        changes_json=json.dumps(changes, ensure_ascii=False) if changes else None,
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
