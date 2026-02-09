from typing import Annotated

from fastapi import Depends, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from itsdangerous import BadSignature, URLSafeTimedSerializer

from app.config import SECRET_KEY, SESSION_COOKIE_NAME
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
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        return None
    data = load_session_token(token)
    if not data:
        return None
    result = await db.execute(select(User).where(User.id == data["user_id"]))
    return result.scalar_one_or_none()


async def require_user(
    request: Request,
    current_user: Annotated[User | None, Depends(get_current_user)],
) -> User:
    if current_user is None:
        return RedirectResponse(
            request.url_for("login_page"),
            status_code=status.HTTP_302_FOUND,
        )
    return current_user


def require_role(*allowed: UserRole):
    async def _check(
        current_user: Annotated[User, Depends(require_user)],
    ) -> User:
        if current_user.role not in allowed:
            from fastapi import HTTPException
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return current_user
    return _check


async def login_user(response: Response, user_id: int) -> None:
    token = create_session_token(user_id)
    response.set_cookie(
        SESSION_COOKIE_NAME,
        token,
        max_age=86400 * 7,
        httponly=True,
        samesite="lax",
    )


def logout_user(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE_NAME)
