from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.database import engine, Base, get_db
from app.routers import auth_router, dashboard_router, assets_router, movements_router, inventory_router, reports_router

app = FastAPI(title="Asset Management")

app.include_router(auth_router.router)
app.include_router(dashboard_router.router)
app.include_router(assets_router.router)
app.include_router(movements_router.router)
app.include_router(inventory_router.router)
app.include_router(reports_router.router)

static_dir = Path(__file__).resolve().parent.parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.on_event("startup")
async def startup():
    from app.config import BASE_DIR, AVATAR_DIR
    (BASE_DIR / "data").mkdir(parents=True, exist_ok=True)
    AVATAR_DIR.mkdir(parents=True, exist_ok=True)
