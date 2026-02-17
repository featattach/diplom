from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth import require_user, require_role
from app.models.user import UserRole, User
from app.templates_ctx import templates
from app.repositories import asset_repo, reference_repo
from app.services.company_service import create_company, update_company, delete_company

router = APIRouter(prefix="", tags=["companies"])


@router.get("/companies", name="companies_list", include_in_schema=False)
async def companies_list(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_user),
):
    companies = await reference_repo.get_companies_ordered(db)
    return templates.TemplateResponse(
        "companies_list.html",
        {"request": request, "user": current_user, "companies": companies},
    )


@router.get("/companies/{company_id:int}", name="company_detail", include_in_schema=False)
async def company_detail(
    request: Request,
    company_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_user),
):
    company = await reference_repo.get_company_by_id(db, company_id)
    if not company:
        raise HTTPException(404, "Organization not found")
    summary = await asset_repo.get_company_asset_summary(db, company_id)
    return templates.TemplateResponse(
        "company_detail.html",
        {
            "request": request,
            "user": current_user,
            "company": company,
            "summary": summary,
        },
    )


@router.get("/companies/create", name="company_create", include_in_schema=False)
async def company_create_form(
    request: Request,
    current_user: User = Depends(require_role(UserRole.admin, UserRole.user)),
):
    return templates.TemplateResponse(
        "company_form.html",
        {"request": request, "user": current_user, "company": None},
    )


@router.post("/companies/create", name="company_create_post", include_in_schema=False)
async def company_create(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin, UserRole.user)),
    name: str = Form(...),
    short_info: str | None = Form(None),
):
    company = await create_company(db, name=name, short_info=short_info)
    return RedirectResponse(url=f"/companies/{company.id}", status_code=302)


@router.get("/companies/{company_id:int}/edit", name="company_edit", include_in_schema=False)
async def company_edit_form(
    request: Request,
    company_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin, UserRole.user)),
):
    company = await reference_repo.get_company_by_id(db, company_id)
    if not company:
        raise HTTPException(404, "Organization not found")
    return templates.TemplateResponse(
        "company_form.html",
        {"request": request, "user": current_user, "company": company},
    )


@router.post("/companies/{company_id:int}/edit", name="company_edit_post", include_in_schema=False)
async def company_edit(
    company_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin, UserRole.user)),
    name: str = Form(...),
    short_info: str | None = Form(None),
):
    company = await reference_repo.get_company_by_id(db, company_id)
    if not company:
        raise HTTPException(404, "Organization not found")
    await update_company(db, company, name=name, short_info=short_info)
    return RedirectResponse(url=f"/companies/{company_id}", status_code=302)


@router.post("/companies/{company_id:int}/delete", name="company_delete", include_in_schema=False)
async def company_delete(
    company_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin, UserRole.user)),
):
    company = await reference_repo.get_company_by_id(db, company_id)
    if not company:
        raise HTTPException(404, "Organization not found")
    await delete_company(db, company)
    return RedirectResponse(url="/inventory", status_code=302)
