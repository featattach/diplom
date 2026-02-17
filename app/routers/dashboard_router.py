from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import INACTIVE_DAYS_THRESHOLD
from app.database import get_db
from app.models.asset import AssetStatus
from app.auth import require_user
from app.models.user import User
from app.templates_ctx import templates
from app.repositories import asset_repo, inventory_repo

router = APIRouter(prefix="", tags=["pages"])


def _days_ago(dt):
    if dt is None:
        return None
    if hasattr(dt, "replace"):
        dt = dt.replace(tzinfo=None) if getattr(dt, "tzinfo", None) else dt
    delta = datetime.utcnow() - dt
    return max(0, delta.days)


def _is_inactive(asset, threshold_days=30):
    if asset.last_seen_at is None:
        return True, None
    days = _days_ago(asset.last_seen_at)
    return (days is not None and days >= threshold_days), days


@router.get("/dashboard", name="dashboard", include_in_schema=False)
async def dashboard(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_user),
):
    now = datetime.utcnow()
    threshold_7 = now - timedelta(days=7)

    all_assets = await asset_repo.get_all_assets_ordered_by_id(db)

    total = len(all_assets)
    by_status = {}
    inactive_list = []
    inactive_by_period = {"0_7": 0, "7_30": 0, "30_plus": 0}
    retired_count = 0
    retired_last_7_days = 0
    devices_requiring_attention = []

    for a in all_assets:
        by_status[a.status] = by_status.get(a.status, 0) + 1
        is_inactive, days_inactive = _is_inactive(a, INACTIVE_DAYS_THRESHOLD)

        if a.status == AssetStatus.retired:
            retired_count += 1
            if a.updated_at and a.updated_at.replace(tzinfo=None) >= threshold_7:
                retired_last_7_days += 1
            devices_requiring_attention.append({
                "asset": a,
                "event_type": "retired",
                "event_label": "списано",
            })
        elif is_inactive:
            inactive_list.append((a, days_inactive or 999))
            d = days_inactive if days_inactive is not None else 999
            if d <= 7:
                inactive_by_period["0_7"] += 1
            elif d <= 30:
                inactive_by_period["7_30"] += 1
            else:
                inactive_by_period["30_plus"] += 1
            devices_requiring_attention.append({
                "asset": a,
                "event_type": "inactive",
                "event_label": f"неактивность {d} дн." if d != 999 else "неактивность 30+ дн.",
            })

    inactive_count = len(inactive_list)
    active_count = total - inactive_count - retired_count
    if active_count < 0:
        active_count = 0

    campaigns_count = await inventory_repo.get_campaigns_count(db)
    movements_pending = 0

    alert_inactive = sum(1 for a in all_assets if _is_inactive(a, INACTIVE_DAYS_THRESHOLD)[0])
    alert_retired_7 = retired_last_7_days
    alert_movements = movements_pending

    total_for_chart = total or 1
    chart_status = {
        "active": round(100 * (by_status.get(AssetStatus.active, 0) / total_for_chart)),
        "inactive": round(100 * (inactive_count / total_for_chart)),
        "retired": round(100 * (retired_count / total_for_chart)),
        "maintenance": round(100 * (by_status.get(AssetStatus.maintenance, 0) / total_for_chart)),
    }
    inactive_total = sum(inactive_by_period.values()) or 1
    chart_inactivity = {
        "0_7": round(100 * inactive_by_period["0_7"] / inactive_total),
        "7_30": round(100 * inactive_by_period["7_30"] / inactive_total),
        "30_plus": round(100 * inactive_by_period["30_plus"] / inactive_total),
    }

    devices_requiring_attention = devices_requiring_attention[:20]

    def _plural(n, one, few, many):
        if n % 10 == 1 and n % 100 != 11:
            return one
        if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14):
            return few
        return many

    alert_lines = []
    if alert_inactive > 0:
        alert_lines.append(f"{alert_inactive} {_plural(alert_inactive, 'устройство', 'устройства', 'устройств')} не {_plural(alert_inactive, 'использовалось', 'использовались', 'использовалось')} более 30 дней")
    if alert_retired_7 > 0:
        alert_lines.append(f"{alert_retired_7} {_plural(alert_retired_7, 'устройство', 'устройства', 'устройств')} {_plural(alert_retired_7, 'было списано', 'были списаны', 'было списано')} за последние 7 дней")
    if alert_movements > 0:
        alert_lines.append(f"{alert_movements} {_plural(alert_movements, 'перемещение', 'перемещения', 'перемещений')} ожидают подтверждения")

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "user": current_user,
            "assets_count": total,
            "campaigns_count": campaigns_count,
            "total_devices": total,
            "active_count": active_count,
            "inactive_count": inactive_count,
            "retired_count": retired_count,
            "retired_last_7_days": retired_last_7_days,
            "alert_inactive": alert_inactive,
            "alert_retired_7": alert_retired_7,
            "alert_movements": alert_movements,
            "devices_requiring_attention": devices_requiring_attention,
            "chart_status": chart_status,
            "chart_inactivity": chart_inactivity,
            "alert_lines": alert_lines,
        },
    )
