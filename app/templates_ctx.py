from pathlib import Path
import contextvars
from datetime import timezone, timedelta
from fastapi.templating import Jinja2Templates

from app.config import DISPLAY_TIMEZONE, DISPLAY_UTC_OFFSET_HOURS
from app.constants import (
    equipment_kind_label,
    status_label,
    event_type_label,
    FLASH_ERROR_MESSAGES,
    TIMEZONE_OPTIONS,
)

# Текущий запрос для доступа к cookie в фильтре (устанавливается middleware)
_request_ctx: contextvars.ContextVar = contextvars.ContextVar("request", default=None)


def _get_display_tz(offset_hours=None):
    """
    Часовой пояс для отображения.
    Если offset_hours задан (из cookie) — timezone(UTC+offset).
    Иначе — ZoneInfo или конфиг по умолчанию (кэш).
    """
    if offset_hours is not None:
        return timezone(timedelta(hours=int(offset_hours)))
    if _get_display_tz._default_tz is not None:
        return _get_display_tz._default_tz
    try:
        from zoneinfo import ZoneInfo
        _get_display_tz._default_tz = ZoneInfo(DISPLAY_TIMEZONE)
    except Exception:
        _get_display_tz._default_tz = timezone(timedelta(hours=DISPLAY_UTC_OFFSET_HOURS))
    return _get_display_tz._default_tz


_get_display_tz._default_tz = None


def get_display_tz_offset():
    """Текущее смещение часового пояса из cookie (для шаблона — какой вариант выбран)."""
    request = _request_ctx.get()
    if not request:
        return None
    raw = request.cookies.get("display_tz_offset")
    if raw is None or raw == "":
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def format_local_time(dt, fmt="%Y-%m-%d %H:%M"):
    """
    Конвертирует datetime в часовой пояс отображения и форматирует.
    Наивные datetime считаются UTC. Часовой пояс берётся из cookie display_tz_offset или из конфига.
    """
    if dt is None:
        return ""
    offset_hours = get_display_tz_offset()
    tz = _get_display_tz(offset_hours=offset_hours)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(tz).strftime(fmt)


_templates_dir = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(_templates_dir))
templates.env.globals["equipment_kind_label"] = equipment_kind_label
templates.env.globals["status_label"] = status_label
templates.env.globals["event_type_label"] = event_type_label
templates.env.globals["flash_error_messages"] = FLASH_ERROR_MESSAGES
templates.env.globals["get_display_tz_offset"] = get_display_tz_offset
templates.env.globals["timezone_options"] = TIMEZONE_OPTIONS
templates.env.filters["format_local_time"] = format_local_time
