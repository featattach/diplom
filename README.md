# Asset Management (FastAPI + Jinja2 + Bootstrap)

Серверное приложение на FastAPI с рендерингом Jinja2 и Bootstrap: учёт оборудования, инвентаризация, отчёты, экспорт в Excel.

## Структура модулей (слои)

После рефакторинга раскладка соответствует трём слоям:

| Слой | Каталог / файлы | Назначение |
|------|------------------|------------|
| **Data** | `models/` | Сущности БД (User, Asset, AssetEvent, Company, InventoryCampaign, InventoryItem). |
| **Data** | `repositories/` | Доступ к БД: `asset_repo`, `inventory_repo`, `reference_repo` (выборки, фильтры, сводки). |
| **Application** | `services/` | Бизнес-логика: `assets_service`, `inventory_service`, `report_service`, `export_xlsx`, `attachments_service`, `company_service`. |
| **Presentation** | `routers/` | HTTP: `assets`, `assets_events`, `inventory_router`, `reports_router`, `qr`, `admin_router`, `auth_router`, `companies_router`, `dashboard_router`, `movements_router`. |

Дополнительно: `constants.py` — подписи и опции для UI; `config.py` — настройки; `auth.py` — сессия, роли, зависимости; `schemas/` — DTO для отчётов.

## Требования

- Python 3.11+
- Виртуальное окружение (рекомендуется)

## Установка и запуск

### 1. Окружение и зависимости

```bash
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

**Если база уже есть, а Alembic ругается «table already exists»** — таблицы созданы без Alembic или таблица `alembic_version` пуста. Пометить базу как актуальную (миграции не выполняются):

```bash
alembic stamp head
```

После этого `alembic upgrade head` больше не будет пытаться создавать существующие таблицы.

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

Разные способы запуска:

| Способ | Команда | Когда использовать |
|--------|--------|--------------------|
| **Разработка (автоперезагрузка)** | `uvicorn app.main:app --reload --host 0.0.0.0 --port 8000` | Редактируете код — сервер перезапускается сам |
| **Через Python** | `python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000` | То же, но uvicorn берётся из текущего окружения |
| **Без перезагрузки** | `uvicorn app.main:app --host 0.0.0.0 --port 8000` | Ближе к «боевому» режиму, быстрее старт |
| **Только localhost** | `uvicorn app.main:app --reload --port 8000` | Доступ только с этого компьютера (по умолчанию host=127.0.0.1) |
| **Скрипт (Windows)** | `.\run.ps1` или `run.bat` | Не нужно каждый раз вводить длинную команду |
| **Docker** | см. раздел «Запуск в Docker» ниже | Запуск в контейнере с той же средой везде |

**Быстрый старт из корня проекта (активирован .venv):**
```powershell
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

## Авторизация и роли

- Сессия в cookie (подпись через itsdangerous), срок жизни 7 дней. Для HTTPS задать `SECURE_COOKIES=true`.
- **Роли:** `admin`, `user`, `viewer`.
  - **admin:** полный доступ, включая пользователей (`/admin/users`), бекапы (`/admin/backups`), создание/редактирование кампаний и активов.
  - **user:** создание и редактирование активов, кампаний, компаний, экспорт, отметки инвентаризации; нет доступа к управлению пользователями и бекапам.
  - **viewer:** только просмотр (списки, карточки, отчёты, экспорт).
- Выход: GET `/logout`. Форма входа защищена CSRF (токен в cookie и в скрытом поле).

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
| `SECURE_COOKIES` | `true` — cookie только по HTTPS (для продакшена) |
| `INACTIVE_DAYS_THRESHOLD` | Порог дней для подсветки неактивных устройств (по умолчанию 30) |
| `MAX_IMPORT_SIZE_MB` | Макс. размер файла импорта оборудования, МБ (по умолчанию 20) |
| `ADMIN_USER` / `ADMIN_PASSWORD` | Логин/пароль при создании admin через `scripts.init_admin` |

## Запуск в Docker

### Сборка и запуск

```bash
docker build -t vkr-app .
docker run -p 8000:8000 vkr-app
```

Без тома используется **новая БД** в контейнере. При первом старте автоматически создаётся пользователь **admin** (пароль: **admin**) — можно сразу войти.

### Подключение своей базы и пользователей

Чтобы использовать **существующие** данные (БД и пользователей с вашего компьютера), при запуске смонтируйте каталог `data` в контейнер. В путях используйте **только прямой слэш** `/`, иначе Docker на Windows может создать лишние папки (например `data;C`).

**MINGW64 / Git Bash (рекомендуется — путь в стиле Unix):**
```bash
docker run -p 8000:8000 -v "$(pwd)/data:/app/data" vkr-app
```
Либо явно:
```bash
docker run -p 8000:8000 -v "/c/Users/root/Documents/vkr/data:/app/data" vkr-app
```

**Windows PowerShell:**
```powershell
docker run -p 8000:8000 -v "${PWD}/data:/app/data" vkr-app
```

В контейнере будет использоваться ваш `data/app.db` и `data/avatars/`. Если появилась папка `data;C` — это артефакт неправильного монтирования (обратный слэш в пути); её можно удалить, данные лежат в обычной папке `data`.

### Создать admin в уже запущенном контейнере (опционально)

Если запускаете без тома и нужен другой пароль для admin, или хотите добавить admin в смонтированную базу (в MINGW64 используйте `$(pwd)/data` с прямым слэшем):

```bash
docker run --rm -it -v "$(pwd)/data:/app/data" vkr-app python -m scripts.init_admin
```

Свой логин/пароль: задайте переменные `ADMIN_USER` и `ADMIN_PASSWORD` в той же команде.

---

## Бекапы

- В интерфейсе: **Администрирование → Бекапы** (`/admin/backups`). Доступно только роли **admin**.
- Создание бекапа: кнопка «Создать бекап» — в `data/backups/` сохраняется zip (БД `app.db`, каталоги `avatars/`, `qrcodes/`).
- Скачивание и восстановление — через ту же страницу. Восстановление перезаписывает текущую БД и каталоги.
- Очистка БД (Drop): удаляет все данные и создаёт одного администратора admin/admin.

## Полезные команды

```bash
# Новая миграция после изменения моделей
alembic revision --autogenerate -m "описание"

# Привести базу к актуальной версии
alembic upgrade head

# Откат на одну миграцию
alembic downgrade -1
```

## Тесты

```bash
pip install pytest pytest-asyncio
pytest tests -v
```

- **Unit:** правила смены статусов активов, генерация событий (AssetEvent), запрет изменения location/current_user для списанного оборудования.
- **Integration:** доступ к `/assets`, `/reports`, экспорт без авторизации (302/401) и с авторизацией (200).
- **Audit trail:** обновление актива создаёт запись в AssetEvent с changes_json.
