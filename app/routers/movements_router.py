from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth import require_user
from app.models.user import User
from app.templates_ctx import templates
from app.repositories import asset_repo

router = APIRouter(prefix="", tags=["pages"])


@router.get("/movements", name="movements", include_in_schema=False)
async def movements(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_user),
):
    events = await asset_repo.get_recent_asset_events(db, limit=500)
    import json
    for e in events:
        e.changes_list = []
        if getattr(e, "changes_json", None):
            try:
                e.changes_list = json.loads(e.changes_json)
            except (TypeError, ValueError, json.JSONDecodeError):
                pass
    return templates.TemplateResponse(
        "movements.html",
        {"request": request, "user": current_user, "events": events},
    )
