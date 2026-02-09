from fastapi import APIRouter, Depends, Request
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Asset, AssetEvent, InventoryCampaign
from app.auth import require_user
from app.models.user import User
from app.templates_ctx import templates

router = APIRouter(prefix="", tags=["pages"])


@router.get("/dashboard", name="dashboard")
async def dashboard(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_user),
):
    assets_count = (await db.execute(select(func.count(Asset.id)))).scalar() or 0
    campaigns_count = (await db.execute(select(func.count(InventoryCampaign.id)))).scalar() or 0
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "user": current_user,
            "assets_count": assets_count,
            "campaigns_count": campaigns_count,
        },
    )
