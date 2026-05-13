from celery import shared_task


@shared_task
def check_pending_posts():
    from .tasks.crosspost import send_all_pending
    return send_all_pending.delay().get(timeout=300)