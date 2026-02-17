from datetime import datetime
from fastapi import APIRouter, Depends, Request, Form, HTTPException, Query
from fastapi.responses import RedirectResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth import require_user, require_role
from app.models.user import User, UserRole
from app.templates_ctx import templates
from app.repositories import asset_repo, reference_repo, inventory_repo
from app.services.export_xlsx import export_inventory_campaign_xlsx
from app.services.inventory_service import (
    mark_asset_found,
    create_campaign,
    update_campaign,
    add_campaign_item,
    mark_item_found_by_id,
    generate_campaign_scope,
    finish_campaign,
)

router = APIRouter(prefix="", tags=["inventory"])


@router.post("/assets/{asset_id:int}/mark-inventory-found", name="asset_mark_inventory_found", include_in_schema=False)
async def asset_mark_inventory_found(
    request: Request,
    asset_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_user),
    campaign_id: int = Form(...),
):
    """Отмечает оборудование как отсканированное (найденное) в рамках кампании инвентаризации."""
    if not await asset_repo.get_asset_by_id(db, asset_id):
        raise HTTPException(404, "Asset not found")
    if not await inventory_repo.get_campaign_by_id(db, campaign_id):
        raise HTTPException(404, "Campaign not found")
    await mark_asset_found(db, campaign_id, asset_id)
    return RedirectResponse(
        request.url_for("asset_detail", asset_id=asset_id) + f"?inventory={campaign_id}&marked=1",
        status_code=303,
    )


@router.get("/inventory", name="inventory_list", include_in_schema=False)
async def inventory_list(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_user),
):
    from datetime import datetime as dt
    companies = await reference_repo.get_companies_with_campaigns(db)
    company_asset_counts = await inventory_repo.get_asset_counts_by_company(db)
    campaigns_without_company = await inventory_repo.get_campaigns_without_company(db)
    company_latest_campaign = {}
    for c in companies:
        if c.campaigns:
            latest = max(c.campaigns, key=lambda x: x.started_at or dt.min)
            company_latest_campaign[c.id] = latest
        else:
            company_latest_campaign[c.id] = None
    return templates.TemplateResponse(
        "inventory_list.html",
        {
            "request": request,
            "user": current_user,
            "companies": companies,
            "company_asset_counts": company_asset_counts,
            "company_latest_campaign": company_latest_campaign,
            "campaigns_without_company": campaigns_without_company,
        },
    )


@router.get("/inventory/{campaign_id:int}", name="inventory_detail", include_in_schema=False)
async def inventory_detail(
    request: Request,
    campaign_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_user),
    scope_generated: str | None = Query(None),
    finished: str | None = Query(None),
):
    campaign = await inventory_repo.get_campaign_with_items(db, campaign_id)
    if not campaign:
        raise HTTPException(404, "Campaign not found")
    assets = await inventory_repo.get_all_assets_ordered(db)
    return templates.TemplateResponse(
        "inventory_detail.html",
        {
            "request": request,
            "user": current_user,
            "campaign": campaign,
            "assets": assets,
            "scope_generated": scope_generated,
            "finished": finished,
        },
    )


@router.post("/inventory/{campaign_id:int}/generate-scope", name="inventory_generate_scope", include_in_schema=False)
async def inventory_generate_scope(
    request: Request,
    campaign_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin, UserRole.user)),
):
    """Формирует объём проверки: снимок активов по организации кампании (или всех). Заменяет текущий список пунктов."""
    campaign = await inventory_repo.get_campaign_by_id(db, campaign_id)
    if not campaign:
        raise HTTPException(404, "Campaign not found")
    try:
        count = await generate_campaign_scope(db, campaign_id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return RedirectResponse(
        request.url_for("inventory_detail", campaign_id=campaign_id) + f"?scope_generated={count}",
        status_code=303,
    )


@router.post("/inventory/{campaign_id:int}/finish", name="inventory_finish", include_in_schema=False)
async def inventory_finish(
    request: Request,
    campaign_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin, UserRole.user)),
):
    """Завершает кампанию (устанавливает дату окончания)."""
    if not await finish_campaign(db, campaign_id):
        raise HTTPException(404, "Campaign not found")
    return RedirectResponse(
        request.url_for("inventory_detail", campaign_id=campaign_id) + "?finished=1",
        status_code=303,
    )


@router.get("/inventory/create", name="inventory_create", include_in_schema=False)
async def inventory_create_form(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin, UserRole.user)),
):
    assets = await inventory_repo.get_all_assets_ordered(db)
    companies = await reference_repo.get_companies_ordered(db)
    return templates.TemplateResponse(
        "inventory_form.html",
        {
            "request": request,
            "user": current_user,
            "campaign": None,
            "assets": assets,
            "companies": companies,
        },
    )


@router.get("/inventory/{campaign_id:int}/edit", name="inventory_campaign_edit", include_in_schema=False)
async def inventory_campaign_edit_form(
    request: Request,
    campaign_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin, UserRole.user)),
):
    campaign = await inventory_repo.get_campaign_by_id(db, campaign_id)
    if not campaign:
        raise HTTPException(404, "Campaign not found")
    assets = await inventory_repo.get_all_assets_ordered(db)
    companies = await reference_repo.get_companies_ordered(db)
    return templates.TemplateResponse(
        "inventory_form.html",
        {
            "request": request,
            "user": current_user,
            "campaign": campaign,
            "assets": assets,
            "companies": companies,
        },
    )


@router.post("/inventory/{campaign_id:int}/edit", name="inventory_edit_post", include_in_schema=False)
async def inventory_campaign_edit(
    campaign_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin, UserRole.user)),
    name: str = Form(...),
    description: str | None = Form(None),
    company_id: str | None = Form(None),
    started_at: str | None = Form(None),
    finished_at: str | None = Form(None),
):
    from datetime import datetime
    campaign = await inventory_repo.get_campaign_by_id(db, campaign_id)
    if not campaign:
        raise HTTPException(404, "Campaign not found")
    started_at_parsed = None
    if started_at and started_at.strip():
        try:
            started_at_parsed = datetime.fromisoformat(started_at.strip().replace("Z", "+00:00"))
        except (ValueError, TypeError):
            pass
    finished_at_parsed = None
    if finished_at and finished_at.strip():
        try:
            finished_at_parsed = datetime.fromisoformat(finished_at.strip().replace("Z", "+00:00"))
        except (ValueError, TypeError):
            pass
    await update_campaign(
        db, campaign,
        name=name.strip(),
        description=description,
        company_id=int(company_id) if company_id and company_id.strip() else None,
        started_at=started_at_parsed,
        finished_at=finished_at_parsed,
    )
    return RedirectResponse(url=f"/inventory/{campaign_id}", status_code=302)


@router.post("/inventory/create", name="inventory_create_post", include_in_schema=False)
async def inventory_create(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin, UserRole.user)),
    name: str = Form(...),
    description: str | None = Form(None),
    company_id: str | None = Form(None),
):
    campaign = await create_campaign(
        db,
        name=name,
        description=description,
        company_id=int(company_id) if company_id and company_id.strip() else None,
    )
    return RedirectResponse(url=f"/inventory/{campaign.id}", status_code=302)


@router.post("/inventory/{campaign_id:int}/item", name="inventory_add_item", include_in_schema=False)
async def inventory_add_item(
    campaign_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin, UserRole.user)),
    asset_id: int | None = Form(None),
    expected_location: str | None = Form(None),
    notes: str | None = Form(None),
):
    campaign = await inventory_repo.get_campaign_by_id(db, campaign_id)
    if not campaign:
        raise HTTPException(404, "Campaign not found")
    await add_campaign_item(
        db, campaign_id,
        asset_id=asset_id if asset_id else None,
        expected_location=expected_location,
        notes=notes,
    )
    return RedirectResponse(url=f"/inventory/{campaign_id}", status_code=302)


@router.post("/inventory/{campaign_id:int}/item/{item_id:int}/found", name="inventory_mark_found", include_in_schema=False)
async def inventory_mark_found(
    campaign_id: int,
    item_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin, UserRole.user)),
):
    if not await mark_item_found_by_id(db, campaign_id, item_id):
        raise HTTPException(404, "Item not found")
    return RedirectResponse(url=f"/inventory/{campaign_id}", status_code=302)


@router.get("/inventory/{campaign_id:int}/export", name="inventory_export", include_in_schema=False)
async def inventory_export(
    campaign_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_user),
):
    campaign = await inventory_repo.get_campaign_with_items(db, campaign_id)
    if not campaign:
        raise HTTPException(404, "Campaign not found")
    items = list(campaign.items)
    buf = export_inventory_campaign_xlsx(campaign, items)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=inventory_{campaign_id}.xlsx"},
    )
