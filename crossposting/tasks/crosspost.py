import logging
import time

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from my_magic_room.models import posts, krissy_blog, box_girl

from ..clients.api import format_post, post
from ..models import CrossPostAttempt

logger = logging.getLogger(__name__)


MODELS = {
    'posts': posts,
    'krissy_blog': krissy_blog,
    'box_girl': box_girl,
}


def log_attempt(post_id, content_type, network, result):
    CrossPostAttempt.objects.create(
        post_id=post_id,
        content_type=content_type,
        network=network,
        status='success' if result.get('ok') else 'failed',
        external_id=result.get('id'),
        error=result.get('error'),
    )


def can_send(obj):
    if obj.publication_status not in ('published', 'delayed_publication'):
        return False

    if obj.publication_status == 'delayed_publication':
        if obj.date_for_publication and obj.date_for_publication > timezone.now():
            return False

    return True


def send_to_all_networks(obj):
    html = obj.description or ''
    ctype = obj._meta.model_name

    config = getattr(settings, 'CROSSPOSTING_CONFIG', {})
    enabled = getattr(settings, 'CROSSPOSTING_ENABLED_NETWORKS', [])

    results = []

    for network in enabled:
        network_config = config.get(network, {})
        if not network_config:
            result = {'network': network, 'ok': False, 'error': 'No config'}
            results.append(result)
            log_attempt(obj.id, ctype, network, result)
            continue

        formatted = format_post(html, obj.title, network, obj.slug, ctype)

        result = post(
            network, network_config,
            formatted['text'],
            formatted.get('link'),
            formatted.get('images', [])
        )

        results.append({'network': network, **result})
        log_attempt(obj.id, ctype, network, result)

    return results


@shared_task(bind=True, max_retries=3)
def send_post(self, content_type, post_id):
    model = MODELS.get(content_type)
    if not model:
        return {'error': f'Unknown type: {content_type}'}

    try:
        obj = model.objects.get(id=post_id)
    except model.DoesNotExist:
        return {'error': f'Not found: {content_type}#{post_id}'}

    if not can_send(obj):
        return {'error': 'Wrong status'}

    results = send_to_all_networks(obj)

    return {
        'post_id': post_id,
        'content_type': content_type,
        'results': results
    }


@shared_task(bind=True)
def send_all_pending(self):
    delay = getattr(settings, 'CROSSPOSTING_DELAY_BETWEEN_POSTS', 2)
    now = timezone.now()
    total = processed = failed = 0
    details = []

    for ctype, model in MODELS.items():
        for obj in model.objects.filter(
            publication_status__in=['published', 'delayed_publication']
        ):
            if obj.publication_status == 'delayed_publication':
                if obj.date_for_publication and obj.date_for_publication > now:
                    continue

            results = send_to_all_networks(obj)

            total += 1
            if all(r.get('ok') for r in results):
                processed += 1
            else:
                failed += 1

            details.append({
                'id': obj.id,
                'type': ctype,
                'results': results
            })

            if delay > 0:
                time.sleep(delay)

    return {
        'total': total,
        'processed': processed,
        'failed': failed,
        'details': details
    }


@shared_task(bind=True)
def send_type(self, content_type):
    model = MODELS.get(content_type)
    if not model:
        return {'error': f'Unknown type: {content_type}'}

    delay = getattr(settings, 'CROSSPOSTING_DELAY_BETWEEN_POSTS', 2)
    now = timezone.now()
    total = processed = failed = 0
    details = []

    for obj in model.objects.filter(
        publication_status__in=['published', 'delayed_publication']
    ):
        if obj.publication_status == 'delayed_publication':
            if obj.date_for_publication and obj.date_for_publication > now:
                continue

        results = send_to_all_networks(obj)

        total += 1
        if all(r.get('ok') for r in results):
            processed += 1
        else:
            failed += 1

        details.append({
            'id': obj.id,
            'results': results
        })

        if delay > 0:
            time.sleep(delay)

    return {
        'type': content_type,
        'total': total,
        'processed': processed,
        'failed': failed,
        'details': details
    }