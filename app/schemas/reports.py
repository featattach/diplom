"""
DTO фильтров для отчётов. Роутер парсит query-параметры в эти модели и передаёт в сервис.
"""
from pydantic import BaseModel, Field


class EquipmentReportFilter(BaseModel):
    """Фильтры отчёта «Оборудование» (список + экспорт Excel)."""
    name: str | None = None
    status: str | None = None
    inactive_by_activity: bool = False
    equipment_kind: str | None = None
    location: str | None = None
    company_id: str | None = None
    sort: str = "newest"

    def sort_value(self) -> str:
        return "newest" if self.sort not in ("newest", "oldest") else self.sort


class TrafficLightReportFilter(BaseModel):
    """Параметры отчёта «Светофор»."""
    company_id: int | None = None
    threshold_years: int = Field(default=5, ge=1, le=20)
