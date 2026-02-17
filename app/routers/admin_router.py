from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, Request, Form, File, UploadFile, HTTPException
from fastapi.responses import RedirectResponse, FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from werkzeug.security import generate_password_hash

from app.config import AVATAR_DIR, ALLOWED_AVATAR_EXTENSIONS, MAX_AVATAR_SIZE_MB
from app.database import get_db, engine
from app.models import User
from app.models.user import UserRole
from app.auth import require_role
from app.templates_ctx import templates
from app.constants import ROLE_CHOICES, ROLE_LABELS
from app.services.backup import create_backup, list_backups, get_backup_path, restore_backup, drop_database

router = APIRouter(prefix="", tags=["admin"])


@router.get("/admin/users", name="admin_users", include_in_schema=False)
async def admin_users_list(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin)),
):
    result = await db.execute(select(User).order_by(User.username))
    users = list(result.scalars().all())
    return templates.TemplateResponse(
        "admin_users.html",
        {
            "request": request,
            "user": current_user,
            "users": users,
            "role_labels": ROLE_LABELS,
        },
    )


@router.get("/admin/users/create", name="admin_user_create", include_in_schema=False)
async def admin_user_create_form(
    request: Request,
    current_user: User = Depends(require_role(UserRole.admin)),
):
    return templates.TemplateResponse(
        "admin_user_create.html",
        {
            "request": request,
            "user": current_user,
            "role_labels": ROLE_LABELS,
            "role_choices": ROLE_CHOICES,
        },
    )


@router.post("/admin/users/create", name="admin_user_create_post", include_in_schema=False)
async def admin_user_create(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin)),
    username: str = Form(...),
    password: str = Form(...),
    password_confirm: str = Form(...),
    role: str = Form("user"),
    is_active: str | None = Form("1"),
):
    if not username or not username.strip():
        return templates.TemplateResponse(
            "admin_user_create.html",
            {
                "request": request,
                "user": current_user,
                "role_labels": ROLE_LABELS,
                "role_choices": ROLE_CHOICES,
                "error": "Введите логин",
            },
            status_code=400,
        )
    username = username.strip()
    if password != password_confirm or not password:
        return templates.TemplateResponse(
            "admin_user_create.html",
            {
                "request": request,
                "user": current_user,
                "role_labels": ROLE_LABELS,
                "role_choices": ROLE_CHOICES,
                "error": "Пароли не совпадают или пусты",
                "username": username,
            },
            status_code=400,
        )
    existing = await db.execute(select(User).where(User.username == username))
    if existing.scalar_one_or_none():
        return templates.TemplateResponse(
            "admin_user_create.html",
            {
                "request": request,
                "user": current_user,
                "role_labels": ROLE_LABELS,
                "role_choices": ROLE_CHOICES,
                "error": "Пользователь с таким логином уже существует",
                "username": username,
            },
            status_code=400,
        )
    role_val = UserRole(role) if role in ROLE_LABELS else UserRole.user
    new_user = User(
        username=username,
        password_hash=generate_password_hash(password),
        role=role_val,
        is_active=is_active == "1",
    )
    db.add(new_user)
    await db.flush()
    return RedirectResponse(url="/admin/users", status_code=302)


@router.post("/admin/users/{user_id:int}/delete", name="admin_user_delete", include_in_schema=False)
async def admin_user_delete(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin)),
):
    from fastapi import HTTPException
    if user_id == current_user.id:
        raise HTTPException(403, "Нельзя удалить свою учётную запись")
    result = await db.execute(select(User).where(User.id == user_id))
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(404, "User not found")
    await db.delete(target)
    await db.flush()
    return RedirectResponse(url="/admin/users", status_code=302)


@router.get("/admin/users/{user_id:int}/edit", name="admin_user_edit", include_in_schema=False)
async def admin_user_edit_form(
    request: Request,
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin)),
):
    result = await db.execute(select(User).where(User.id == user_id))
    target = result.scalar_one_or_none()
    if not target:
        from fastapi import HTTPException
        raise HTTPException(404, "User not found")
    is_self = target.id == current_user.id
    return templates.TemplateResponse(
        "admin_user_edit.html",
        {
            "request": request,
            "user": current_user,
            "target_user": target,
            "role_labels": ROLE_LABELS,
            "role_choices": ROLE_CHOICES,
            "is_self": is_self,
            "max_size_mb": MAX_AVATAR_SIZE_MB,
            "allowed_extensions": ", ".join(ALLOWED_AVATAR_EXTENSIONS),
        },
    )


@router.post("/admin/users/{user_id:int}/avatar", name="admin_user_avatar_upload", include_in_schema=False)
async def admin_user_avatar_upload(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin)),
    file: UploadFile = File(...),
):
    from fastapi import HTTPException
    result = await db.execute(select(User).where(User.id == user_id))
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(404, "User not found")
    if not file.filename:
        return RedirectResponse(url=f"/admin/users/{user_id}/edit?error=no_file", status_code=302)
    ext = Path(file.filename).suffix.lstrip(".").lower()
    if ext not in ALLOWED_AVATAR_EXTENSIONS:
        return RedirectResponse(url=f"/admin/users/{user_id}/edit?error=bad_type", status_code=302)
    content = await file.read()
    if len(content) > MAX_AVATAR_SIZE_MB * 1024 * 1024:
        return RedirectResponse(url=f"/admin/users/{user_id}/edit?error=too_big", status_code=302)
    AVATAR_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{target.id}_{int(datetime.utcnow().timestamp())}.{ext}"
    path = AVATAR_DIR / filename
    with open(path, "wb") as f:
        f.write(content)
    target.avatar = filename
    await db.flush()
    return RedirectResponse(url=f"/admin/users/{user_id}/edit", status_code=302)


@router.post("/admin/users/{user_id:int}/edit", name="admin_user_edit_post", include_in_schema=False)
async def admin_user_edit(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin)),
    role: str | None = Form(None),
    is_active: str | None = Form(None),
    new_password: str | None = Form(None),
    new_password_confirm: str | None = Form(None),
):
    result = await db.execute(select(User).where(User.id == user_id))
    target = result.scalar_one_or_none()
    if not target:
        from fastapi import HTTPException
        raise HTTPException(404, "User not found")
    is_self = target.id == current_user.id

    if role and role in ROLE_LABELS and not is_self:
        target.role = UserRole(role)
    target.is_active = is_active == "1"

    if new_password and new_password.strip() and new_password == new_password_confirm:
        target.password_hash = generate_password_hash(new_password.strip())

    await db.flush()
    return RedirectResponse(url="/admin/users", status_code=302)


# ——— Бекапы ———

@router.get("/admin/backups", name="admin_backups", include_in_schema=False)
async def admin_backups_page(
    request: Request,
    current_user: User = Depends(require_role(UserRole.admin)),
):
    backups = list_backups()
    return templates.TemplateResponse(
        "admin_backups.html",
        {
            "request": request,
            "user": current_user,
            "backups": backups,
        },
    )


@router.post("/admin/backups/create", name="admin_backup_create", include_in_schema=False)
async def admin_backup_create(
    current_user: User = Depends(require_role(UserRole.admin)),
):
    name = create_backup()
    return RedirectResponse(url=f"/admin/backups?created={name}", status_code=302)


@router.get("/admin/backups/download/{filename}", name="admin_backup_download", include_in_schema=False)
async def admin_backup_download(
    filename: str,
    current_user: User = Depends(require_role(UserRole.admin)),
):
    path = get_backup_path(filename)
    if not path:
        raise HTTPException(404, "Бекап не найден")
    return FileResponse(
        path,
        filename=filename,
        media_type="application/zip",
    )


@router.post("/admin/backups/restore", name="admin_backup_restore", include_in_schema=False)
async def admin_backup_restore(
    request: Request,
    current_user: User = Depends(require_role(UserRole.admin)),
    filename: str = Form(...),
    confirm: str = Form(None),
):
    if confirm != "yes":
        return RedirectResponse(url="/admin/backups?error=confirm", status_code=302)
    path = get_backup_path(filename)
    if not path:
        raise HTTPException(404, "Бекап не найден")
    try:
        await engine.dispose()
        restore_backup(filename)
    except Exception as e:
        raise HTTPException(500, f"Ошибка восстановления: {e}")
    return RedirectResponse(url="/admin/backups?restored=1", status_code=302)


@router.post("/admin/backups/drop", name="admin_backup_drop", include_in_schema=False)
async def admin_backup_drop(
    current_user: User = Depends(require_role(UserRole.admin)),
    confirm: str = Form(None),
):
    """Очистить базу: удалить все данные и создать пустую БД с одним админом (admin/admin)."""
    if confirm != "yes":
        return RedirectResponse(url="/admin/backups?error=drop_confirm", status_code=302)
    try:
        await engine.dispose()
        drop_database()
    except Exception as e:
        raise HTTPException(500, f"Ошибка очистки базы: {e}")
    return RedirectResponse(url="/login?dropped=1", status_code=302)
