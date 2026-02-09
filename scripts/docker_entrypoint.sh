#!/bin/sh
set -e
cd /app

# Миграции
alembic upgrade head

# Если в базе нет ни одного пользователя — создаём admin (логин: admin, пароль: admin)
python -m scripts.ensure_admin_if_empty

exec uvicorn app.main:app --host 0.0.0.0 --port 8000
