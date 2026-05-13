import logging

from django.core.management.base import BaseCommand

from crossposting.tasks.crosspost import send_post
from my_magic_room.models import posts, krissy_blog, box_girl

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Тест кросспостинга одного поста'

    def add_arguments(self, parser):
        parser.add_argument('--type', choices=['posts', 'krissy_blog', 'box_girl'])
        parser.add_argument('--id', type=int)
        parser.add_argument('--list', action='store_true')

    def handle(self, *args, **options):
        if options['list']:
            self.list_posts()
            return

        ctype = options.get('type')
        post_id = options.get('id')

        if not ctype or not post_id:
            self.stdout.write('Usage: test_crosspost --type posts --id 1')
            return

        self.stdout.write(f'Sending {ctype}#{post_id}...')

        try:
            result = send_post.delay(ctype, post_id).get(timeout=60)
            self.stdout.write(self.style.SUCCESS(result))
        except Exception as e:
            self.stdout.write(self.style.ERROR(str(e)))
            logger.exception("test_crosspost failed")

    def list_posts(self):
        models = {'posts': posts, 'krissy_blog': krissy_blog, 'box_girl': box_girl}

        for ctype, model in models.items():
            self.stdout.write(f'\n[{ctype}]')

            items = model.objects.filter(
                publication_status__in=['published', 'delayed_publication']
            )

            if not items:
                self.stdout.write('  Nothing to send')
                continue

            for obj in items:
                date = f' (due: {obj.date_for_publication})' if obj.date_for_publication else ''
                self.stdout.write(f'  [{obj.id}] {obj.title[:50]}{date}')