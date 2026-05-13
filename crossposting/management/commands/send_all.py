import logging

from django.core.management.base import BaseCommand

from crossposting.tasks.crosspost import send_all_pending

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Отправить все готовые посты'

    def handle(self, *args, **options):
        self.stdout.write('Processing all pending posts...')

        try:
            result = send_all_pending.delay().get(timeout=300)

            self.stdout.write(self.style.SUCCESS(
                f"Done. Total: {result['total']}, "
                f"OK: {result['processed']}, "
                f"Failed: {result['failed']}"
            ))
        except Exception as e:
            self.stdout.write(self.style.ERROR(str(e)))
            logger.exception("send_all failed")