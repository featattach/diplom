# Запуск в контейнере и перенос на другой сервер

## 1. Собрать образ на своей машине

В корне проекта (где лежит `Dockerfile`):

```bash
docker build -t vkr-app .
```

Если сборка падает с ошибкой про образ Python (например, `python:3.14-slim` не найден), откройте `Dockerfile` и замените первую строку на:

```dockerfile
FROM python:3.12-slim
```

затем снова выполните `docker build -t vkr-app .`.

---

## 2. Запуск у себя (проверка)

**Только контейнер (данные внутри контейнера, при удалении контейнера пропадут):**

```bash
docker run -p 8000:8000 --name vkr vkr-app
```

Откройте в браузере: http://localhost:8000  
При первом старте создаётся пользователь **admin** / **admin**.

**С сохранением данных на хост** (рекомендуется): каталог `data` монтируется в контейнер, БД и бекапы остаются на диске.

Windows (PowerShell):

```powershell
docker run -p 8000:8000 -v "${PWD}/data:/app/data" --name vkr vkr-app
```

Linux / macOS:

```bash
docker run -p 8000:8000 -v "$(pwd)/data:/app/data" --name vkr vkr-app
```

Остановка: `docker stop vkr`. Запуск снова: `docker start vkr`.

---

## 3. Перенос на другой сервер

### Вариант А: через файл образа (без Docker Registry)

**На исходной машине** — сохранить образ в файл:

```bash
docker save -o vkr-app.tar vkr-app
```

Перенесите файл `vkr-app.tar` на другой сервер (SCP, флешка, облако и т.п.).

**На целевом сервере** — установите Docker (если ещё не установлен), затем:

```bash
docker load -i vkr-app.tar
```

После этого образ `vkr-app` будет доступен локально.

### Вариант Б: через реестр Docker (Docker Hub и т.п.)

На исходной машине:

```bash
docker tag vkr-app ваш-login/vkr-app:latest
docker push ваш-login/vkr-app:latest
```

На целевом сервере:

```bash
docker pull ваш-login/vkr-app:latest
docker tag ваш-login/vkr-app:latest vkr-app
```

---

## 4. Запуск на другом сервере

### Минимальный запуск

1. Убедитесь, что Docker установлен: `docker --version`.

2. Создайте каталог для данных (если используете том):

   ```bash
   mkdir -p /opt/vkr/data
   ```

3. Запустите контейнер:

   **С локальным каталогом данных:**

   ```bash
   docker run -d \
     -p 8000:8000 \
     -v /opt/vkr/data:/app/data \
     --name vkr \
     --restart unless-stopped \
     vkr-app
   ```

   **Без тома** (все данные внутри контейнера):

   ```bash
   docker run -d -p 8000:8000 --name vkr --restart unless-stopped vkr-app
   ```

4. Проверьте: откройте в браузере `http://IP-сервера:8000`. Логин по умолчанию: **admin** / **admin**.

### Переменные окружения (по желанию)

Чтобы задать свой секретный ключ сессии и порт:

```bash
docker run -d \
  -p 9000:8000 \
  -v /opt/vkr/data:/app/data \
  -e SECRET_KEY="ваш-длинный-секретный-ключ-минимум-32-символа" \
  --name vkr \
  --restart unless-stopped \
  vkr-app
```

Здесь приложение слушает снаружи порт **9000** (`-p 9000:8000`).

### Полезные команды на сервере

| Действие              | Команда |
|-----------------------|--------|
| Логи контейнера      | `docker logs vkr` |
| Логи в реальном времени | `docker logs -f vkr` |
| Остановить            | `docker stop vkr` |
| Запустить снова       | `docker start vkr` |
| Перезапустить         | `docker restart vkr` |
| Удалить контейнер     | `docker stop vkr && docker rm vkr` |

---

## 5. Восстановление из бекапа на новом сервере

Если на старом сервере вы делали бекап через интерфейс (Администрирование → Бекапы):

1. Скопируйте скачанный файл `backup_YYYY-MM-DD_HH-MM-SS.zip` на новый сервер в каталог данных, например:
   ```bash
   # на новом сервере
   mkdir -p /opt/vkr/data/backups
   # скопируйте backup_....zip в /opt/vkr/data/backups/
   ```

2. Запустите контейнер с томом `-v /opt/vkr/data:/app/data`.

3. Войдите как admin, откройте **Администрирование → Бекапы**, нажмите **Восстановить** у нужного бекапа (файл должен быть в `data/backups/` внутри контейнера, т.е. в `/opt/vkr/data/backups/` на хосте).

Либо положите только `app.db` в `/opt/vkr/data/app.db`, перезапустите контейнер — приложение будет работать с этой базой.

---

## Краткая шпаргалка

**Сборка и экспорт образа:**

```bash
docker build -t vkr-app .
docker save -o vkr-app.tar vkr-app
```

**На другом сервере:**

```bash
docker load -i vkr-app.tar
mkdir -p /opt/vkr/data
docker run -d -p 8000:8000 -v /opt/vkr/data:/app/data --name vkr --restart unless-stopped vkr-app
```

После этого приложение доступно по адресу `http://IP:8000`, данные хранятся в `/opt/vkr/data`.
