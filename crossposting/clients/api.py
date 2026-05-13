import logging
import re
from html import unescape
from urllib.parse import urlparse

import requests
from django.conf import settings
from django.contrib.sites.models import Site
from django.template.defaultfilters import striptags

logger = logging.getLogger(__name__)


def get_allowed_domains():
    return getattr(settings, 'CROSSPOSTING_ALLOWED_IMAGE_DOMAINS', []) or []


def is_url_allowed(url):
    allowed = get_allowed_domains()
    if not allowed:
        return True

    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        for allowed_domain in allowed:
            if domain == allowed_domain.lower() or domain.endswith('.' + allowed_domain.lower()):
                return True
    except:
        pass

    return False


def get_site_url():
    try:
        return f"https://{Site.objects.get_current().domain}"
    except:
        return getattr(settings, 'BASE_URL', 'https://example.com')


def html_to_text(html):
    text = striptags(html or '')
    text = unescape(text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def extract_images(html):
    if not html:
        return []

    site_url = get_site_url()
    images = []

    for match in re.finditer(r'<img[^>]+src=["\']([^"\']+)["\']', html, re.IGNORECASE):
        src = match.group(1)

        if src.startswith('//'):
            src = 'https:' + src
        elif src.startswith('/'):
            src = site_url + src

        if src.startswith('http') and is_url_allowed(src):
            images.append(src)

    return images


def extract_link(html, slug, content_type):
    site_url = get_site_url()

    match = re.search(r'<a[^>]+href=["\']([^"\']+)["\']', html, re.IGNORECASE)
    if match:
        href = match.group(1)
        if href.startswith('//'):
            return 'https:' + href
        if href.startswith('/'):
            return site_url + href
        return href

    return f"{site_url}/{content_type}/{slug}/"


def get_limits():
    defaults = {
        'telegram': {'text': 4096, 'images': 10},
        'x': {'text': 280, 'images': 4},
        'twitter': {'text': 280, 'images': 4},
        'facebook': {'text': 63206, 'images': 1},
        'instagram': {'text': 2200, 'images': 1},
    }
    custom = getattr(settings, 'CROSSPOSTING_LIMITS', {})
    for network in defaults:
        if network in custom:
            defaults[network].update(custom[network])
    return defaults


def format_post(html, title, network, slug=None, content_type=None):
    limits = get_limits()
    lim = limits.get(network.lower(), {'text': 1000, 'images': 1})

    text = html_to_text(html)
    if title:
        text = f"{title}\n\n{text}"

    # режем до лимита, не разрывая слова (иначе убого выглядит)
    if len(text) > lim['text']:
        text = text[:lim['text']-3].rsplit(' ', 1)[0] + '...'

    images = extract_images(html)[:lim['images']]  # картинки тоже лимитируем

    link = None
    if slug and content_type:
        link = extract_link(html, slug, content_type)

    return {
        'text': text,
        'images': images,
        'link': link
    }


def send_telegram(token, chat_id, text, link=None):
    if not token or not chat_id:
        logger.warning("Telegram: missing token or chat_id")
        return {'ok': False, 'error': 'Missing credentials'}

    try:
        full_text = text
        if link:
            full_text = f"{text}\n\nЧитать далее: {link}"

        response = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={
                'chat_id': chat_id,
                'text': full_text[:4096],
                'parse_mode': 'HTML'
            },
            timeout=30
        )
        result = response.json()

        if result.get('ok'):
            return {'ok': True, 'id': result['result']['message_id']}

        return {'ok': False, 'error': result.get('description', 'Unknown')}

    except Exception as e:
        logger.exception("Telegram failed")
        return {'ok': False, 'error': str(e)}


def send_telegram_photo(token, chat_id, text, image_url, link=None):
    if not token or not chat_id:
        logger.warning("Telegram photo: missing token or chat_id")
        return {'ok': False, 'error': 'Missing credentials'}

    try:
        caption = text
        if link:
            caption = f"{text}\n\nЧитать далее: {link}"

        response = requests.post(
            f"https://api.telegram.org/bot{token}/sendPhoto",
            json={
                'chat_id': chat_id,
                'photo': image_url,
                'caption': caption[:1024],
                'parse_mode': 'HTML'
            },
            timeout=60
        )
        result = response.json()

        if result.get('ok'):
            return {'ok': True, 'id': result['result']['message_id']}

        return {'ok': False, 'error': result.get('description')}

    except Exception as e:
        logger.exception("Telegram photo failed")
        return {'ok': False, 'error': str(e)}


def upload_twitter_image(image_url, bearer_token):
    if not bearer_token:
        logger.warning("Twitter upload: missing bearer_token")
        return None

    if not is_url_allowed(image_url):
        logger.warning(f"Twitter upload: domain not allowed {image_url}")
        return None

    try:
        img = requests.get(image_url, timeout=30)
        if img.status_code != 200:
            return None

        response = requests.post(
            "https://upload.twitter.com/1.1/media-upload.json",
            files={'media': img.content},
            headers={'Authorization': f'Bearer {bearer_token}'},
            timeout=60
        )
        return response.json().get('media_id_string')
    except:
        return None


def send_x(bearer_token, text, images=None):
    if not bearer_token:
        logger.warning("X send: missing bearer_token")
        return {'ok': False, 'error': 'Missing credentials'}

    try:
        payload = {'text': text[:280]}

        if images:
            media_ids = [upload_twitter_image(img, bearer_token) for img in images[:4]]
            media_ids = [m for m in media_ids if m]
            if media_ids:
                payload['media'] = {'media_ids': media_ids}

        response = requests.post(
            "https://api.twitter.com/2/tweets",
            json=payload,
            headers={'Authorization': f'Bearer {bearer_token}'},
            timeout=30
        )
        result = response.json()

        if response.status_code == 201:
            return {'ok': True, 'id': result['data']['id']}

        return {'ok': False, 'error': result['errors'][0]['message']}

    except Exception as e:
        logger.exception("X failed")
        return {'ok': False, 'error': str(e)}


def send_facebook(token, page_id, text, link=None, image_url=None):
    if not token or not page_id:
        logger.warning("Facebook send: missing credentials")
        return {'ok': False, 'error': 'Missing credentials'}

    api_version = getattr(settings, 'CROSSPOSTING_FACEBOOK_API_VERSION', 'v18.0')

    try:
        base_url = f"https://graph.facebook.com/{api_version}/{page_id}"

        if image_url:
            if not is_url_allowed(image_url):
                logger.warning(f"Facebook: domain not allowed {image_url}")
                return {'ok': False, 'error': 'Image domain not allowed'}

            response = requests.post(
                f"{base_url}/photos",
                data={
                    'url': image_url,
                    'caption': text[:63206],
                    'access_token': token
                },
                timeout=60
            )
        else:
            payload = {'message': text[:63206], 'access_token': token}
            if link:
                payload['link'] = link
            response = requests.post(f"{base_url}/feed", data=payload, timeout=30)

        result = response.json()

        if 'id' in result:
            return {'ok': True, 'id': result['id']}

        return {'ok': False, 'error': result.get('error', {}).get('message', 'Unknown')}

    except Exception as e:
        logger.exception("Facebook failed")
        return {'ok': False, 'error': str(e)}


def send_instagram(token, ig_user_id, text, image_url):
    if not token or not ig_user_id:
        logger.warning("Instagram send: missing credentials")
        return {'ok': False, 'error': 'Missing credentials'}

    if not is_url_allowed(image_url):
        logger.warning(f"Instagram: domain not allowed {image_url}")
        return {'ok': False, 'error': 'Image domain not allowed'}

    api_version = getattr(settings, 'CROSSPOSTING_INSTAGRAM_API_VERSION', 'v18.0')

    try:
        base_url = f"https://graph.facebook.com/{api_version}/{ig_user_id}"

        container = requests.post(
            f"{base_url}/media",
            data={
                'caption': text[:2200],
                'image_url': image_url,
                'access_token': token
            },
            timeout=60
        ).json()

        if 'id' not in container:
            return {'ok': False, 'error': 'Container failed'}

        publish = requests.post(
            f"{base_url}/media_publish",
            data={
                'creation_id': container['id'],
                'access_token': token
            },
            timeout=60
        ).json()

        if 'id' in publish:
            return {'ok': True, 'id': publish['id']}

        return {'ok': False, 'error': 'Publish failed'}

    except Exception as e:
        logger.exception("Instagram failed")
        return {'ok': False, 'error': str(e)}


def post(network, config, text, link=None, images=None):
    if network == 'telegram':
        if images:
            return send_telegram_photo(
                config.get('TELEGRAM_BOT_TOKEN'),
                config.get('TELEGRAM_CHAT_ID'),
                text, images[0], link
            )
        return send_telegram(
            config.get('TELEGRAM_BOT_TOKEN'),
            config.get('TELEGRAM_CHAT_ID'),
            text, link
        )

    if network in ('x', 'twitter'):
        return send_x(
            config.get('X_BEARER_TOKEN') or config.get('X_ACCESS_TOKEN'),
            text, images
        )

    if network == 'facebook':
        return send_facebook(
            config.get('FACEBOOK_ACCESS_TOKEN'),
            config.get('FACEBOOK_PAGE_ID'),
            text, link, images[0] if images else None
        )

    if network == 'instagram':
        if not images:
            return {'ok': False, 'error': 'Instagram requires image'}
        return send_instagram(
            config.get('INSTAGRAM_ACCESS_TOKEN'),
            config.get('INSTAGRAM_USER_ID'),
            text, images[0]
        )

    return {'ok': False, 'error': f'Unknown network: {network}'}