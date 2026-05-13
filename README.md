# Кросспостинг в соцсети

## Структура

```
crossposting/
├── clients/api.py          # API соцсетей
├── tasks/crosspost.py      # Celery задачи
├── models.py               # Логи отправок
├── admin.py                # Админка
├── schedules.py            # Beat планировщик
└── management/commands/    # Команды для тестирования
```

## Установка

1. Скопировать папку `crossposting/` в проект

2. Добавить в `settings.py`:

```python
INSTALLED_APPS = [
    ...
    'crossposting',
]

# Celery
CELERY_BROKER_URL = 'redis://localhost:6379/0'
CELERY_RESULT_BACKEND = 'redis://localhost:6379/0'

# Включённые сети
CROSSPOSTING_ENABLED_NETWORKS = ['telegram']

# Конфиг соцсетей
CROSSPOSTING_CONFIG = {
    'telegram': {
        'TELEGRAM_BOT_TOKEN': env('TELEGRAM_BOT_TOKEN'),
        'TELEGRAM_CHAT_ID': env('TELEGRAM_CHAT_ID'),
    },
}

# Домены для картинок (безопасность)
CROSSPOSTING_ALLOWED_IMAGE_DOMAINS = ['example.com']
```

3. Добавить в `celery.py`:

```python
from .celery import app as celery_app
```

4. Миграции:

```bash
python manage.py makemigrations crossposting
python manage.py migrate
```

5. Запуск:

```bash
# Celery worker
celery -A main worker -l info

# Celery beat (автоматическая отправка каждые 5 минут)
celery -A main beat -l info
```

## Команды

```bash
# Тест одного поста
python manage.py test_crosspost --type posts --id 1

# Список готовых постов
python manage.py test_crosspost --list

# Отправить все
python manage.py send_all

# Отправить по типу
python manage.py send_type posts
```
