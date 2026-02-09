from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import RedirectResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Company, Asset
from app.models.asset import AssetStatus
from app.auth import require_user, require_role
from app.models.user import UserRole, User
from app.templates_ctx import templates

router = APIRouter(prefix="", tags=["companies"])


async def _company_summary(db: AsyncSession, company_id: int):
    """Сводка по технике организации: количество по статусам и по расположению."""
    total = (await db.execute(select(func.count(Asset.id)).where(Asset.company_id == company_id))).scalar() or 0
    by_status = await db.execute(
        select(Asset.status, func.count(Asset.id))
        .where(Asset.company_id == company_id)
        .group_by(Asset.status)
    )
    status_counts = dict(by_status.all())
    by_location = await db.execute(
        select(Asset.location, func.count(Asset.id))
        .where(Asset.company_id == company_id)
        .where(Asset.location.isnot(None))
        .where(Asset.location != "")
        .group_by(Asset.location)
        .order_by(func.count(Asset.id).desc())
        .limit(20)
    )
    location_counts = list(by_location.all())
    return {
        "total": total,
        "status_counts": status_counts,
        "location_counts": location_counts,
    }


@router.get("/companies", name="companies_list")
async def companies_list(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_user),
):
    result = await db.execute(select(Company).order_by(Company.name))
    companies = list(result.scalars().all())
    return templates.TemplateResponse(
        "companies_list.html",
        {"request": request, "user": current_user, "companies": companies},
    )


@router.get("/companies/{company_id:int}", name="company_detail")
async def company_detail(
    request: Request,
    company_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_user),
):
    result = await db.execute(select(Company).where(Company.id == company_id))
    company = result.scalar_one_or_none()
    if not company:
        from fastapi import HTTPException
        raise HTTPException(404, "Organization not found")
    summary = await _company_summary(db, company_id)
    status_labels = {"active": "Активно", "inactive": "Неактивно", "maintenance": "На обслуживании", "retired": "Списано"}
    return templates.TemplateResponse(
        "company_detail.html",
        {
            "request": request,
            "user": current_user,
            "company": company,
            "summary": summary,
            "status_labels": status_labels,
        },
    )


@router.get("/companies/create", name="company_create")
async def company_create_form(
    request: Request,
    current_user: User = Depends(require_role(UserRole.admin, UserRole.user)),
):
    return templates.TemplateResponse(
        "company_form.html",
        {"request": request, "user": current_user, "company": None},
    )


@router.post("/companies/create", name="company_create_post")
async def company_create(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin, UserRole.user)),
    name: str = Form(...),
    short_info: str | None = Form(None),
):
    company = Company(name=name.strip(), short_info=short_info.strip() if short_info else None)
    db.add(company)
    await db.flush()
    return RedirectResponse(url=f"/companies/{company.id}", status_code=302)


@router.get("/companies/{company_id:int}/edit", name="company_edit")
async def company_edit_form(
    request: Request,
    company_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin, UserRole.user)),
):
    result = await db.execute(select(Company).where(Company.id == company_id))
    company = result.scalar_one_or_none()
    if not company:
        from fastapi import HTTPException
        raise HTTPException(404, "Organization not found")
    return templates.TemplateResponse(
        "company_form.html",
        {"request": request, "user": current_user, "company": company},
    )


@router.post("/companies/{company_id:int}/edit", name="company_edit_post")
async def company_edit(
    company_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin, UserRole.user)),
    name: str = Form(...),
    short_info: str | None = Form(None),
):
    result = await db.execute(select(Company).where(Company.id == company_id))
    company = result.scalar_one_or_none()
    if not company:
        from fastapi import HTTPException
        raise HTTPException(404, "Organization not found")
    company.name = name.strip()
    company.short_info = short_info.strip() if short_info else None
    await db.flush()
    return RedirectResponse(url=f"/companies/{company_id}", status_code=302)


@router.post("/companies/{company_id:int}/delete", name="company_delete")
async def company_delete(
    company_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin, UserRole.user)),
):
    from fastapi import HTTPException
    result = await db.execute(select(Company).where(Company.id == company_id))
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(404, "Organization not found")
    await db.delete(company)
    await db.flush()
    return RedirectResponse(url="/inventory", status_code=302)
