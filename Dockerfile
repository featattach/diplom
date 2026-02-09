# Система учёта оборудования — запуск в контейнере
FROM python:3.14-slim

WORKDIR /app

# Зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Код приложения
COPY alembic.ini .
COPY alembic ./alembic
COPY app ./app
COPY static ./static
COPY templates ./templates
COPY scripts ./scripts

# Каталог для БД и загрузок (при монтировании тома данные сохраняются)
ENV PYTHONUNBUFFERED=1
RUN mkdir -p /app/data /app/data/avatars

# Скрипт старта: миграции, при необходимости создание admin, затем uvicorn
COPY scripts/docker_entrypoint.sh /app/scripts/docker_entrypoint.sh
RUN sed -i 's/\r$//' /app/scripts/docker_entrypoint.sh && chmod +x /app/scripts/docker_entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/app/scripts/docker_entrypoint.sh"]
