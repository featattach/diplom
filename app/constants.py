"""
Единый источник истины для лейблов, опций и справочных значений.
Используется в роутерах, сервисах и шаблонах (через контекст).
"""

# --- Статусы актива (AssetStatus) ---
STATUS_LABELS = {
    "active": "Активно",
    "inactive": "Неактивно",
    "maintenance": "На обслуживании",
    "retired": "Списано",
}


def status_label(status) -> str:
    """Единая точка: enum статуса или строка -> подпись для отображения (шаблоны, экспорт)."""
    if status is None:
        return "—"
    val = status.value if hasattr(status, "value") else status
    return STATUS_LABELS.get(val, val or "—")


# --- Типы событий (AssetEventType) ---
EVENT_TYPE_LABELS = {
    "created": "Создание",
    "updated": "Изменение",
    "moved": "Перемещение",
    "assigned": "Назначение",
    "returned": "Возврат",
    "maintenance": "Обслуживание",
    "retired": "Списание",
    "other": "Прочее",
}
EVENT_TYPE_OPTIONS = [{"value": k, "label": v} for k, v in EVENT_TYPE_LABELS.items()]


def event_type_label(event_type) -> str:
    """Единая точка: enum типа события или строка -> подпись для отображения."""
    if event_type is None:
        return "—"
    val = event_type.value if hasattr(event_type, "value") else event_type
    return EVENT_TYPE_LABELS.get(val, val or "—")


# --- Типы техники (EquipmentKind / equipment_kind) ---
EQUIPMENT_KIND_LABELS = {
    "desktop": "Системный блок",
    "nettop": "Неттоп",
    "laptop": "Ноутбук",
    "monitor": "Монитор",
    "mfu": "МФУ",
    "printer": "Принтер",
    "scanner": "Сканер",
    "switch": "Коммутатор",
    "server": "Сервер",
    "sip_phone": "SIP-телефон",
    "monoblock": "Моноблок",
}
EQUIPMENT_KIND_CHOICES = [{"value": k, "label": v} for k, v in EQUIPMENT_KIND_LABELS.items()]


def equipment_kind_label(ek) -> str:
    """Единая точка: enum или строка -> подпись для отображения. Использовать в шаблонах и экспорте."""
    if ek is None:
        return "—"
    val = ek.value if hasattr(ek, "value") else ek
    return EQUIPMENT_KIND_LABELS.get(val, val or "—")

# Обратный маппинг: подпись в файле импорта -> value в БД
EQUIPMENT_KIND_LABELS_TO_VALUE = {
    "системный блок": "desktop",
    "неттоп": "nettop",
    "ноутбук": "laptop",
    "монитор": "monitor",
    "мфу": "mfu",
    "принтер": "printer",
    "сканер": "scanner",
    "коммутатор": "switch",
    "сервер": "server",
    "sip-телефон": "sip_phone",
    "моноблок": "monoblock",
}

# Группы типов техники (для условного отображения полей в формах)
EQUIPMENT_KIND_HAS_SCREEN = ("laptop", "monitor")
EQUIPMENT_KIND_NEEDS_RACK = ("server",)
EQUIPMENT_KIND_HAS_TECH = ("desktop", "nettop", "laptop", "server")
EQUIPMENT_KIND_HAS_OS = ("desktop", "nettop", "laptop", "server")
EQUIPMENT_KIND_HAS_MANUFACTURE_DATE = ("desktop", "nettop", "laptop", "server")

# --- ОС ---
OS_OPTIONS = [
    {"value": "linux", "label": "Linux"},
    {"value": "windows_7", "label": "Windows 7"},
    {"value": "windows_10", "label": "Windows 10"},
    {"value": "windows_11", "label": "Windows 11"},
]

# --- Подписи полей актива (для журнала «было → стало») ---
ASSET_FIELD_LABELS = {
    "name": "Название",
    "serial_number": "Серийный номер",
    "asset_type": "Категория",
    "equipment_kind": "Тип техники",
    "model": "Модель",
    "location": "Расположение",
    "status": "Статус",
    "description": "Описание",
    "last_seen_at": "Последняя активность",
    "cpu": "Процессор",
    "ram": "ОЗУ",
    "disk1_type": "Тип диска",
    "disk1_capacity": "Объём диска",
    "network_card": "IP адрес",
    "motherboard": "Материнская плата",
    "screen_diagonal": "Диагональ экрана",
    "screen_resolution": "Разрешение экрана",
    "power_supply": "Блок питания",
    "monitor_diagonal": "Монитор (диагональ)",
    "rack_units": "Юниты (U)",
    "company_id": "Организация",
    "os": "ОС",
    "network_interfaces": "Сетевые интерфейсы",
    "current_user": "Пользователь (кто использует)",
    "manufacture_date": "Дата выпуска",
}

# --- Доп. устройства (блок в форме актива) ---
EXTRA_COMPONENT_TYPES = [
    {"value": "cpu", "label": "Процессор"},
    {"value": "ram", "label": "ОЗУ"},
    {"value": "disk", "label": "Диск"},
    {"value": "network_card", "label": "IP адрес"},
    {"value": "other", "label": "Прочее"},
]

# --- Роли пользователя (UserRole) ---
ROLE_LABELS = {
    "admin": "Администратор",
    "user": "Пользователь",
    "viewer": "Наблюдатель",
}
ROLE_CHOICES = [{"value": k, "label": v} for k, v in ROLE_LABELS.items()]

# --- Коды ошибок для JSON-ответов ---
HTTP_STATUS_TO_CODE = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    422: "validation_error",
    500: "server_error",
}

# --- Сообщения для flash/alert по query-параметру error= (HTML-страницы) ---
FLASH_ERROR_MESSAGES = {
    "no_file": "Выберите файл.",
    "bad_type": "Недопустимый формат файла.",
    "too_big": "Файл слишком большой.",
    "confirm": "Для выполнения действия требуется подтверждение.",
    "drop_confirm": "Для очистки базы данных требуется подтверждение.",
}
