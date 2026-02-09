from fastapi import APIRouter, Depends, Request
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Asset, InventoryCampaign
from app.models.asset import AssetStatus
from app.auth import require_user
from app.models.user import User
from app.templates_ctx import templates

router = APIRouter(prefix="", tags=["reports"])

STATUS_LABELS = {
    "active": "Активно", "inactive": "Неактивно",
    "maintenance": "На обслуживании", "retired": "Списано",
}


@router.get("/reports", name="reports")
async def reports(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_user),
):
    total_assets = (await db.execute(select(func.count(Asset.id)))).scalar() or 0
    by_status = await db.execute(
        select(Asset.status, func.count(Asset.id)).group_by(Asset.status)
    )
    status_counts = dict(by_status.all())
    total_campaigns = (await db.execute(select(func.count(InventoryCampaign.id)))).scalar() or 0
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
