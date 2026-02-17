"""Генерация и выдача QR-кодов, страница сканирования."""
from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import RedirectResponse, FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth import require_user
from app.models.user import User
from app.templates_ctx import templates
from app.repositories import asset_repo, inventory_repo
from app.services.attachments_service import generate_qr_for_asset, get_qr_path

router = APIRouter(prefix="", tags=["qr"])


@router.get("/assets/{asset_id:int}/qr-image", name="asset_qr_image", include_in_schema=False)
async def asset_qr_image(
    asset_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_user),
):
    """Отдаёт PNG QR-кода для актива (если сгенерирован)."""
    path = get_qr_path(asset_id)
    if not path.is_file():
        raise HTTPException(404, "QR-код не сгенерирован")
    if not await asset_repo.get_asset_by_id(db, asset_id):
        raise HTTPException(404, "Asset not found")
    return FileResponse(path, media_type="image/png")


@router.post("/assets/{asset_id:int}/generate-qr", name="asset_generate_qr", include_in_schema=False)
async def asset_generate_qr(
    request: Request,
    asset_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_user),
):
    """Генерирует или перезаписывает QR-код для актива, редирект на карточку."""
    if not await asset_repo.get_asset_by_id(db, asset_id):
        raise HTTPException(404, "Asset not found")
    base_url = str(request.base_url).rstrip("/")
    generate_qr_for_asset(asset_id, base_url)
    return RedirectResponse(
        request.url_for("asset_detail", asset_id=asset_id),
        status_code=303,
    )


@router.get("/scan", name="scan_qr", include_in_schema=False)
async def scan_qr_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_user),
):
    """Страница сканирования QR-кода камерой (для перехода на карточку и отметки «отсканировано»)."""
    campaigns = await inventory_repo.get_active_campaigns(db)
    return templates.TemplateResponse(
        "scan.html",
        {"request": request, "user": current_user, "campaigns": campaigns},
    )
