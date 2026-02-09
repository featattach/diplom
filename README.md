# Asset Management (FastAPI + Jinja2 + Bootstrap)

Серверное приложение на FastAPI с рендерингом Jinja2 и Bootstrap.

## Требования

- Python 3.11+
- Виртуальное окружение (рекомендуется)

## Установка и запуск

### 1. Окружение и зависимости

```bash
cd c:\Users\root\Documents\vkr
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 2. База данных и миграции

Каталог `data` создаётся автоматически при первом запуске (или при миграциях).

```bash
# Применить миграции Alembic (создаёт таблицы)
alembic upgrade head
```

### 3. Создание администратора

```bash
# Логин: admin, пароль: admin
python -m scripts.init_admin

# Свой логин/пароль (переменные окружения)
set ADMIN_USER=myadmin
set ADMIN_PASSWORD=mysecret
python -m scripts.init_admin
```

### 4. Запуск сервера

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Откройте в браузере: http://127.0.0.1:8000  
Страница входа: http://127.0.0.1:8000/login

## Страницы

| Путь | Описание |
|------|----------|
| `/login` | Вход (cookie-session) |
| `/dashboard` | Сводка |
| `/assets` | Список активов + фильтры + экспорт XLSX |
| `/assets/{id}` | Карточка актива, история событий, добавление события |
| `/movements` | Журнал перемещений/событий |
| `/inventory` | Список инвентаризационных кампаний |
| `/inventory/{id}` | Кампания: пункты, экспорт XLSX |
| `/reports` | Отчёты и экспорты |

## Модели (SQLAlchemy)

- **User** — пользователь (username, password_hash, role: admin/user/viewer)
- **Asset** — актив (name, serial_number, asset_type, location, status, last_seen_at, …)
- **AssetEvent** — событие по активу (event_type, description, created_at, …)
- **InventoryCampaign** — кампания инвентаризации
- **InventoryItem** — пункт инвентаризации (связь с активом, found, notes)

## Авторизация

- Сессия в cookie (подпись через itsdangerous), срок жизни 7 дней.
- Роли: `admin`, `user`, `viewer`. Проверка через `require_role(UserRole.admin)` при необходимости.
- Выход: GET `/logout`.

## Неактивные устройства

Устройства считаются неактивными, если `last_seen_at` отсутствует или старше порога (по умолчанию 30 дней, задаётся `INACTIVE_DAYS_THRESHOLD`). На странице списка активов такие строки подсвечиваются (жёлтый фон).

## Экспорт XLSX

- Список активов: кнопка «Export XLSX» на `/assets` или ссылка на `/assets/export`.
- Кампания инвентаризации: кнопка «Export XLSX» на странице `/inventory/{id}` или `/inventory/{id}/export`.

## Переменные окружения

| Переменная | Описание |
|------------|----------|
| `DATABASE_URL` | URL БД (по умолчанию SQLite в `data/app.db`) |
| `SECRET_KEY` | Ключ подписи сессии (обязательно сменить в проде) |
| `INACTIVE_DAYS_THRESHOLD` | Порог дней для подсветки неактивных устройств (по умолчанию 30) |
| `ADMIN_USER` / `ADMIN_PASSWORD` | Логин/пароль при создании admin через `scripts.init_admin` |

## Полезные команды

```bash
# Новая миграция после изменения моделей
alembic revision --autogenerate -m "описание"

# Откат на одну миграцию
alembic downgrade -1
```
