from pathlib import Path
from fastapi.templating import Jinja2Templates

from app.constants import (
    equipment_kind_label,
    status_label,
    event_type_label,
    FLASH_ERROR_MESSAGES,
)

_templates_dir = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(_templates_dir))
templates.env.globals["equipment_kind_label"] = equipment_kind_label
templates.env.globals["status_label"] = status_label
templates.env.globals["event_type_label"] = event_type_label
templates.env.globals["flash_error_messages"] = FLASH_ERROR_MESSAGES
