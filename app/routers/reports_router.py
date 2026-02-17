from datetime import UTC, datetime
from fastapi import APIRouter, Depends, Request, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import INACTIVE_DAYS_THRESHOLD
from app.database import get_db
from app.models.asset import AssetStatus
from app.auth import require_user
from app.models.user import User
from app.templates_ctx import templates
from app.constants import EQUIPMENT_KIND_CHOICES, EQUIPMENT_KIND_LABELS, STATUS_LABELS
from app.utils.asset_helpers import is_asset_inactive
from app.repositories import asset_repo, reference_repo, inventory_repo
from app.schemas.reports import EquipmentReportFilter, TrafficLightReportFilter
from app.services.report_service import (
    build_traffic_light_rows,
    export_equipment_xlsx,
    export_traffic_light_xlsx,
)

router = APIRouter(prefix="", tags=["reports"])


@router.get("/reports", name="reports", include_in_schema=False)
async def reports(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_user),
):
    total_assets = await asset_repo.get_total_assets_count(db)
    status_counts = await asset_repo.get_asset_status_counts(db)
    total_campaigns = await inventory_repo.get_campaigns_count(db)
    return templates.TemplateResponse(
        "reports.html",
        {
            "request": request,
            "user": current_user,
            "total_assets": total_assets,
            "status_counts": status_counts,
            "status_enum": AssetStatus,
            "status_labels": STATUS_LABELS,
            "total_campaigns": total_campaigns,
        },
    )


def _equipment_filter_from_query(
    name: str | None,
    status: str | None,
    inactive_by_activity: bool,
    equipment_kind: str | None,
    location: str | None,
    company_id: str | None,
    sort: str | None,
) -> EquipmentReportFilter:
    sort_val = "newest" if sort not in ("newest", "oldest") else sort
    return EquipmentReportFilter(
        name=name,
        status=status,
        inactive_by_activity=inactive_by_activity,
        equipment_kind=equipment_kind,
        location=location or None,
        company_id=company_id or None,
        sort=sort_val,
    )


@router.get("/reports/equipment", name="reports_equipment", include_in_schema=False)
async def reports_equipment(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_user),
    name: str | None = Query(None),
    status: str | None = Query(None),
    inactive_by_activity: bool = Query(False, description="Неактивные по последней активности"),
    equipment_kind: str | None = Query(None),
    location: str | None = Query(None),
    company_id: str | None = Query(None),
    sort: str | None = Query("newest"),
):
    filters = _equipment_filter_from_query(name, status, inactive_by_activity, equipment_kind, location, company_id, sort)
    assets = await asset_repo.get_assets_list(
        db,
        name=filters.name,
        status=filters.status,
        inactive_by_activity=filters.inactive_by_activity,
        equipment_kind=filters.equipment_kind,
        location=filters.location,
        company_id=filters.company_id,
        sort=filters.sort_value(),
    )
    if filters.inactive_by_activity:
        assets = [a for a in assets if is_asset_inactive(a)]
    companies = await reference_repo.get_companies_ordered(db)
    location_choices = await asset_repo.get_distinct_locations(db)
    qp = {
        k: v
        for k, v in [
            ("name", name),
            ("status", status),
            ("inactive_by_activity", "1" if inactive_by_activity else None),
            ("equipment_kind", equipment_kind),
            ("location", location or ""),
            ("company_id", company_id or ""),
            ("sort", filters.sort_value() if filters.sort_value() != "newest" else None),
        ]
        if v is not None and v != ""
    }
    base_export_url = request.url_for("reports_equipment_export")
    export_url = str(base_export_url.include_query_params(**qp)) if qp else str(base_export_url)
    return templates.TemplateResponse(
        "reports_equipment.html",
        {
            "request": request,
            "user": current_user,
            "assets": assets,
            "companies": companies,
            "location_choices": location_choices,
            "export_url": export_url,
            "filters": {"name": filters.name, "status": filters.status, "inactive_by_activity": filters.inactive_by_activity, "equipment_kind": filters.equipment_kind, "location": filters.location or "", "company_id": filters.company_id or "", "sort": filters.sort_value()},
            "status_enum": AssetStatus,
            "status_labels": STATUS_LABELS,
            "equipment_kind_choices": EQUIPMENT_KIND_CHOICES,
            "equipment_kind_labels": EQUIPMENT_KIND_LABELS,
            "is_inactive_fn": is_asset_inactive,
            "inactive_days_threshold": INACTIVE_DAYS_THRESHOLD,
        },
    )


@router.get("/reports/equipment/export.xlsx", name="reports_equipment_export", include_in_schema=False)
async def reports_equipment_export(
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
    filters = _equipment_filter_from_query(name, status, inactive_by_activity, equipment_kind, location, company_id, sort)
    buf = await export_equipment_xlsx(
        db,
        filters,
        generated_by=current_user.username or str(current_user.id),
        generated_at=datetime.now(UTC),
    )
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=equipment.xlsx"},
    )


def _traffic_light_filter_from_query(company_id: str | None, threshold_years: int) -> TrafficLightReportFilter:
    company_id_int = None
    if company_id and str(company_id).strip():
        try:
            company_id_int = int(company_id.strip())
        except ValueError:
            pass
    return TrafficLightReportFilter(company_id=company_id_int, threshold_years=threshold_years)


@router.get("/reports/traffic-light", name="reports_traffic_light", include_in_schema=False)
async def reports_traffic_light(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_user),
    company_id: str | None = Query(None, description="Организация"),
    threshold_years: int = Query(5, ge=1, le=20, description="Порог устаревания (лет), красный цвет"),
):
    filters = _traffic_light_filter_from_query(company_id, threshold_years)
    companies = await reference_repo.get_companies_ordered(db)
    assets = await asset_repo.get_traffic_light_assets(db, filters.company_id)
    rows = build_traffic_light_rows(assets, filters.threshold_years)
    return templates.TemplateResponse(
        "reports_traffic_light.html",
        {
            "request": request,
            "user": current_user,
            "companies": companies,
            "company_id": filters.company_id,
            "threshold_years": filters.threshold_years,
            "rows": rows,
            "equipment_kind_labels": EQUIPMENT_KIND_LABELS,
        },
    )


@router.get("/reports/traffic-light/export.xlsx", name="reports_traffic_light_export", include_in_schema=False)
async def reports_traffic_light_export(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_user),
    company_id: str | None = Query(None, description="Организация"),
    threshold_years: int = Query(5, ge=1, le=20, description="Порог устаревания (лет)"),
):
    filters = _traffic_light_filter_from_query(company_id, threshold_years)
    buf = await export_traffic_light_xlsx(
        db,
        filters,
        generated_by=current_user.username or str(current_user.id),
        generated_at=datetime.now(UTC),
    )
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=traffic_light.xlsx"},
    )
