from typing import Annotated

from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from itsdangerous import BadSignature, URLSafeTimedSerializer

from app.config import SECRET_KEY, SESSION_COOKIE_NAME, SECURE_COOKIES
from app.database import get_db
from app.models import User
from app.models.user import UserRole

serializer = URLSafeTimedSerializer(SECRET_KEY)


def create_session_token(user_id: int) -> str:
    return serializer.dumps({"user_id": user_id})


def load_session_token(token: str) -> dict | None:
    try:
        return serializer.loads(token, max_age=86400 * 7)  # 7 days
    except BadSignature:
        return None


async def get_current_user(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User | None:
    """Загружает пользователя из сессии. Возвращает None, если не авторизован."""
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        return None
    data = load_session_token(token)
    if not data:
        return None
    result = await db.execute(select(User).where(User.id == data["user_id"]))
    return result.scalar_one_or_none()


async def require_user(
    current_user: Annotated[User | None, Depends(get_current_user)],
) -> User:
    """Зависимость: возвращает User или выбрасывает HTTPException(401)."""
    if current_user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return current_user


def get_optional_user(
    current_user: Annotated[User | None, Depends(get_current_user)],
) -> User | None:
    """Зависимость для эндпоинтов, где пользователь опционален (возвращает User или None)."""
    return current_user


def require_role(*allowed: UserRole):
    async def _check(
        current_user: Annotated[User, Depends(require_user)],
    ) -> User:
        if current_user.role not in allowed:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return current_user
    return _check


def _cookie_kwargs() -> dict:
    """Общие параметры cookie (path, secure, samesite) для установки и удаления."""
    return {
        "path": "/",
        "secure": SECURE_COOKIES,
        "samesite": "lax",
    }


async def login_user(response: Response, user_id: int) -> None:
    token = create_session_token(user_id)
    response.set_cookie(
        SESSION_COOKIE_NAME,
        token,
        max_age=86400 * 7,
        httponly=True,
        **_cookie_kwargs(),
    )


def logout_user(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE_NAME, path="/", secure=SECURE_COOKIES, samesite="lax")
