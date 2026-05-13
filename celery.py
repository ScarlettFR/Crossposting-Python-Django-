from celery import Celery
from celery.schedules import crontab

app = Celery('main')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

app.conf.beat_schedule = {
    'check-pending-posts': {
        'task': 'crossposting.schedules.check_pending_posts',
        'schedule': crontab(minute='*/5'),
    },
}