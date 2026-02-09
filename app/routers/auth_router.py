from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, Request, Form, UploadFile, File
from fastapi.responses import RedirectResponse, HTMLResponse, FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from werkzeug.security import check_password_hash

from app.config import AVATAR_DIR, ALLOWED_AVATAR_EXTENSIONS, MAX_AVATAR_SIZE_MB
from app.database import get_db
from app.models import User
from app.auth import get_current_user, require_user, require_role, login_user, logout_user
from app.models.user import UserRole
from app.templates_ctx import templates

router = APIRouter(prefix="", tags=["auth"])


@router.get("/login", name="login_page")
async def login_page(
    request: Request,
    current_user: User | None = Depends(get_current_user),
):
    if current_user:
        return RedirectResponse("/dashboard", status_code=302)
    return templates.TemplateResponse(
        "login.html",
        {"request": request, "user": None},
    )


@router.post("/login")
async def login(
    request: Request,
    db: AsyncSession = Depends(get_db),
    username: str = Form(...),
    password: str = Form(...),
):
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if not user or not check_password_hash(user.password_hash, password):
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "user": None, "error": "Неверный логин или пароль"},
            status_code=401,
        )
    if not getattr(user, "is_active", True):
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "user": None, "error": "Учётная запись заблокирована"},
            status_code=403,
        )
    res = RedirectResponse("/dashboard", status_code=302)
    await login_user(res, user.id)
    return res


@router.get("/logout", name="logout")
async def logout(request: Request):
    res = RedirectResponse("/login", status_code=302)
    logout_user(res)
    return res


@router.get("/profile/avatar", name="profile_avatar")
async def profile_avatar_form(
    request: Request,
    current_user: User = Depends(require_user),
):
    return templates.TemplateResponse(
        "profile_avatar.html",
        {
            "request": request,
            "user": current_user,
            "max_size_mb": MAX_AVATAR_SIZE_MB,
            "allowed_extensions": ", ".join(ALLOWED_AVATAR_EXTENSIONS),
        },
    )


@router.post("/profile/avatar", name="profile_avatar_upload")
async def profile_avatar_upload(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin, UserRole.user)),
    file: UploadFile = File(...),
):
    if not file.filename:
        return RedirectResponse("/profile/avatar?error=no_file", status_code=302)
    ext = Path(file.filename).suffix.lstrip(".").lower()
    if ext not in ALLOWED_AVATAR_EXTENSIONS:
        return RedirectResponse("/profile/avatar?error=bad_type", status_code=302)
    content = await file.read()
    if len(content) > MAX_AVATAR_SIZE_MB * 1024 * 1024:
        return RedirectResponse("/profile/avatar?error=too_big", status_code=302)
    AVATAR_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{current_user.id}_{int(datetime.utcnow().timestamp())}.{ext}"
    path = AVATAR_DIR / filename
    with open(path, "wb") as f:
        f.write(content)
    current_user.avatar = filename
    await db.flush()
    return RedirectResponse("/profile/avatar", status_code=302)


@router.get("/uploads/avatars/{filename}", name="avatar_file")
async def avatar_file(filename: str):
    path = AVATAR_DIR / filename
    if not path.is_file():
        from fastapi import HTTPException
        raise HTTPException(404, "Not found")
    return FileResponse(path)
