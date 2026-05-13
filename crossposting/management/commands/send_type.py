import logging

from django.core.management.base import BaseCommand

from crossposting.tasks.crosspost import send_type

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Отправить все посты одного типа'

    def add_arguments(self, parser):
        parser.add_argument('content_type', choices=['posts', 'krissy_blog', 'box_girl'])

    def handle(self, *args, **options):
        ctype = options['content_type']

        try:
            result = send_type.delay(ctype).get(timeout=300)

            self.stdout.write(self.style.SUCCESS(
                f"Done. Total: {result['total']}, "
                f"OK: {result['processed']}, "
                f"Failed: {result['failed']}"
            ))
        except Exception as e:
            self.stdout.write(self.style.ERROR(str(e)))
            logger.exception("send_type failed")