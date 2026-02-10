from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import AssetEvent
from app.auth import require_user
from app.models.user import User
from app.templates_ctx import templates

router = APIRouter(prefix="", tags=["pages"])

EVENT_TYPE_LABELS = {
    "created": "Создание", "updated": "Изменение", "moved": "Перемещение",
    "assigned": "Назначение", "returned": "Возврат", "maintenance": "Обслуживание",
    "retired": "Списание", "other": "Прочее",
}


@router.get("/movements", name="movements")
async def movements(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_user),
):
    result = await db.execute(
        select(AssetEvent)
        .options(selectinload(AssetEvent.asset))
        .order_by(AssetEvent.created_at.desc())
        .limit(500)
    )
    events = list(result.scalars().all())
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
        {
            "request": request,
            "user": current_user,
            "events": events,
            "event_type_labels": EVENT_TYPE_LABELS,
        },
    )
