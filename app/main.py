from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.database import engine, Base, get_db
from app.routers import auth_router, dashboard_router, assets_router, movements_router, inventory_router, reports_router, admin_router, companies_router

app = FastAPI(title="Asset Management")

app.include_router(auth_router.router)
app.include_router(dashboard_router.router)
app.include_router(assets_router.router)
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


@app.on_event("startup")
async def startup():
    from app.config import BASE_DIR, AVATAR_DIR, QR_DIR, BACKUP_DIR
    (BASE_DIR / "data").mkdir(parents=True, exist_ok=True)
    AVATAR_DIR.mkdir(parents=True, exist_ok=True)
    QR_DIR.mkdir(parents=True, exist_ok=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
