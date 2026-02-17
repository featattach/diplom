from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import HTTPException

from app.database import engine, Base, get_db
from app.routers import (
    auth_router,
    dashboard_router,
    assets,
    assets_events,
    qr,
    movements_router,
    inventory_router,
    reports_router,
    admin_router,
    companies_router,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Создание каталогов data, avatars, qrcodes, backups при старте."""
    from app.config import BASE_DIR, AVATAR_DIR, QR_DIR, BACKUP_DIR
    (BASE_DIR / "data").mkdir(parents=True, exist_ok=True)
    AVATAR_DIR.mkdir(parents=True, exist_ok=True)
    QR_DIR.mkdir(parents=True, exist_ok=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(title="Asset Management", lifespan=lifespan)


def _accepts_html(request: Request) -> bool:
    accept = request.headers.get("accept", "").lower()
    return "text/html" in accept


def _error_code_from_exception(exc: HTTPException) -> str:
    """Код ошибки для JSON-ответа: из exc.detail (если dict с ключом code) или по status_code."""
    from app.constants import HTTP_STATUS_TO_CODE
    if isinstance(getattr(exc, "detail", None), dict) and "code" in exc.detail:
        return exc.detail["code"]
    return HTTP_STATUS_TO_CODE.get(exc.status_code, "error")


def _detail_for_json(exc: HTTPException):
    """Текст для поля detail: строка или список (validation)."""
    d = getattr(exc, "detail", None)
    if isinstance(d, dict) and "message" in d:
        return d["message"]
    return d


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """401 + HTML → редирект на логин. Остальное → JSON с полями detail и code."""
    if exc.status_code == 401 and _accepts_html(request):
        return RedirectResponse(
            request.url_for("login_page"),
            status_code=302,
        )
    from fastapi.responses import JSONResponse
    content = {
        "detail": _detail_for_json(exc),
        "code": _error_code_from_exception(exc),
    }
    return JSONResponse(status_code=exc.status_code, content=content)


app.include_router(auth_router.router)
app.include_router(dashboard_router.router)
app.include_router(assets.router)
app.include_router(assets_events.router)
app.include_router(qr.router)
app.include_router(movements_router.router)
app.include_router(inventory_router.router)
app.include_router(companies_router.router)
app.include_router(reports_router.router)
app.include_router(admin_router.router)

static_dir = Path(__file__).resolve().parent.parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    """Иконка вкладки: браузер по умолчанию запрашивает /favicon.ico."""
    return RedirectResponse(url="/static/favicon.svg")