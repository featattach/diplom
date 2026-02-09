from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import RedirectResponse, StreamingResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import InventoryCampaign, InventoryItem, Asset, Company
from app.auth import require_user, require_role
from app.models.user import User, UserRole
from app.templates_ctx import templates
from app.services.export_xlsx import export_inventory_campaign_xlsx

router = APIRouter(prefix="", tags=["inventory"])


@router.get("/inventory", name="inventory_list")
async def inventory_list(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_user),
):
    from sqlalchemy.orm import selectinload
    companies_result = await db.execute(
        select(Company)
        .order_by(Company.name)
        .options(selectinload(Company.campaigns))
    )
    companies = list(companies_result.scalars().all())
    company_asset_counts = {}
    if companies:
        counts_result = await db.execute(
            select(Asset.company_id, func.count(Asset.id))
            .where(Asset.company_id.isnot(None))
            .group_by(Asset.company_id)
        )
        company_asset_counts = dict(counts_result.all())
    campaigns_without_company_result = await db.execute(
        select(InventoryCampaign)
        .where(InventoryCampaign.company_id.is_(None))
        .order_by(InventoryCampaign.started_at.desc())
    )
    campaigns_without_company = list(campaigns_without_company_result.scalars().all())
    from datetime import datetime as dt
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


@router.get("/inventory/{campaign_id:int}", name="inventory_detail")
async def inventory_detail(
    request: Request,
    campaign_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_user),
):
    result = await db.execute(
        select(InventoryCampaign)
        .where(InventoryCampaign.id == campaign_id)
        .options(selectinload(InventoryCampaign.items).selectinload(InventoryItem.asset))
    )
    campaign = result.scalar_one_or_none()
    if not campaign:
        from fastapi import HTTPException
        raise HTTPException(404, "Campaign not found")
    assets_result = await db.execute(select(Asset).order_by(Asset.name))
    assets = list(assets_result.scalars().all())
    return templates.TemplateResponse(
        "inventory_detail.html",
        {
            "request": request,
            "user": current_user,
            "campaign": campaign,
            "assets": assets,
        },
    )


@router.get("/inventory/create", name="inventory_create")
async def inventory_create_form(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin, UserRole.user)),
):
    result = await db.execute(select(Asset).order_by(Asset.name))
    assets = list(result.scalars().all())
    companies_result = await db.execute(select(Company).order_by(Company.name))
    companies = list(companies_result.scalars().all())
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


@router.get("/inventory/{campaign_id:int}/edit", name="inventory_campaign_edit")
async def inventory_campaign_edit_form(
    request: Request,
    campaign_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin, UserRole.user)),
):
    result = await db.execute(select(InventoryCampaign).where(InventoryCampaign.id == campaign_id))
    campaign = result.scalar_one_or_none()
    if not campaign:
        from fastapi import HTTPException
        raise HTTPException(404, "Campaign not found")
    assets_result = await db.execute(select(Asset).order_by(Asset.name))
    assets = list(assets_result.scalars().all())
    companies_result = await db.execute(select(Company).order_by(Company.name))
    companies = list(companies_result.scalars().all())
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


@router.post("/inventory/{campaign_id:int}/edit", name="inventory_edit_post")
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
    result = await db.execute(select(InventoryCampaign).where(InventoryCampaign.id == campaign_id))
    campaign = result.scalar_one_or_none()
    if not campaign:
        from fastapi import HTTPException
        raise HTTPException(404, "Campaign not found")
    campaign.name = name.strip()
    campaign.description = description.strip() if description else None
    campaign.company_id = int(company_id) if company_id and company_id.strip() else None
    if started_at and started_at.strip():
        try:
            campaign.started_at = datetime.fromisoformat(started_at.strip().replace("Z", "+00:00"))
        except (ValueError, TypeError):
            pass
    else:
        campaign.started_at = None
    if finished_at and finished_at.strip():
        try:
            campaign.finished_at = datetime.fromisoformat(finished_at.strip().replace("Z", "+00:00"))
        except (ValueError, TypeError):
            pass
    else:
        campaign.finished_at = None
    await db.flush()
    return RedirectResponse(url=f"/inventory/{campaign_id}", status_code=302)


@router.post("/inventory/create", name="inventory_create_post")
async def inventory_create(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin, UserRole.user)),
    name: str = Form(...),
    description: str | None = Form(None),
    company_id: str | None = Form(None),
):
    campaign = InventoryCampaign(
        name=name,
        description=description if description else None,
        company_id=int(company_id) if company_id and company_id.strip() else None,
    )
    db.add(campaign)
    await db.flush()
    return RedirectResponse(url=f"/inventory/{campaign.id}", status_code=302)


@router.post("/inventory/{campaign_id:int}/item", name="inventory_add_item")
async def inventory_add_item(
    campaign_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin, UserRole.user)),
    asset_id: int | None = Form(None),
    expected_location: str | None = Form(None),
    notes: str | None = Form(None),
):
    result = await db.execute(select(InventoryCampaign).where(InventoryCampaign.id == campaign_id))
    campaign = result.scalar_one_or_none()
    if not campaign:
        from fastapi import HTTPException
        raise HTTPException(404, "Campaign not found")
    item = InventoryItem(
        campaign_id=campaign_id,
        asset_id=asset_id if asset_id else None,
        expected_location=expected_location if expected_location else None,
        notes=notes if notes else None,
    )
    db.add(item)
    await db.flush()
    return RedirectResponse(url=f"/inventory/{campaign_id}", status_code=302)


@router.post("/inventory/{campaign_id:int}/item/{item_id:int}/found", name="inventory_mark_found")
async def inventory_mark_found(
    campaign_id: int,
    item_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin, UserRole.user)),
):
    from datetime import datetime
    result = await db.execute(
        select(InventoryItem)
        .where(InventoryItem.id == item_id)
        .where(InventoryItem.campaign_id == campaign_id)
    )
    item = result.scalar_one_or_none()
    if not item:
        from fastapi import HTTPException
        raise HTTPException(404, "Item not found")
    item.found = True
    item.found_at = datetime.utcnow()
    await db.flush()
    return RedirectResponse(url=f"/inventory/{campaign_id}", status_code=302)


@router.get("/inventory/{campaign_id:int}/export", name="inventory_export")
async def inventory_export(
    campaign_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_user),
):
    result = await db.execute(
        select(InventoryCampaign)
        .where(InventoryCampaign.id == campaign_id)
        .options(selectinload(InventoryCampaign.items).selectinload(InventoryItem.asset))
    )
    campaign = result.scalar_one_or_none()
    if not campaign:
        from fastapi import HTTPException
        raise HTTPException(404, "Campaign not found")
    items = list(campaign.items)
    buf = export_inventory_campaign_xlsx(campaign, items)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=inventory_{campaign_id}.xlsx"},
    )
