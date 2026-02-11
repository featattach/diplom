# Система учёта оборудования — запуск в контейнере
FROM python:3.12-slim

WORKDIR /app

# Системные библиотеки для сборки Pillow (qrcode, изображения)
RUN apt-get update && apt-get install -y --no-install-recommends \
    zlib1g-dev \
    libjpeg-dev \
    libpng-dev \
    && rm -rf /var/lib/apt/lists/*

# Зависимости Python
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
