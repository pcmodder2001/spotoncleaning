"""SiteMatrix subscription / site live status checks."""

import json
import logging
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

CACHE_KEY = 'sitematrix:site_status'


def _debug(message, *args):
    if getattr(settings, 'SITEMATRIX_DEBUG', False):
        logger.info('[SiteMatrix] ' + message, *args)


def _masked_key():
    key = settings.SITEMATRIX_API_KEY
    if not key:
        return '(not set)'
    if len(key) <= 8:
        return '****'
    return f'{key[:4]}...{key[-4:]}'


def log_startup_status():
    """Log configuration once when checks are enabled."""
    if not getattr(settings, 'SITEMATRIX_DEBUG', False):
        return
    if settings.SITEMATRIX_ENABLED:
        _debug(
            'ENABLED — %s (key: %s, timeout: %ss).',
            settings.SITEMATRIX_STATUS_URL,
            _masked_key(),
            settings.SITEMATRIX_TIMEOUT_SECONDS,
        )
        _debug(
            'Active sites: cache %ss. When OFF: API every request. DEBUG=True: API every request always.',
            settings.SITEMATRIX_CACHE_SECONDS,
        )
    else:
        _debug(
            'DISABLED — set SITEMATRIX_STATUS_URL and SITEMATRIX_API_KEY in .env to enable.'
        )


def fetch_site_status():
    """Return parsed JSON from SiteMatrix, or None if unreachable (fail open)."""
    url = settings.SITEMATRIX_STATUS_URL
    api_key = settings.SITEMATRIX_API_KEY
    if not url or not api_key:
        _debug('Skipping API call — URL or API key not configured.')
        return None

    _debug('Sending GET %s (key: %s, timeout: %ss)', url, _masked_key(), settings.SITEMATRIX_TIMEOUT_SECONDS)

    request = Request(
        url,
        headers={
            'X-Site-API-Key': api_key,
            'Accept': 'application/json',
        },
        method='GET',
    )
    try:
        with urlopen(request, timeout=settings.SITEMATRIX_TIMEOUT_SECONDS) as response:
            status = response.status
            raw_body = response.read().decode()
            _debug('Response HTTP %s — body: %s', status, raw_body)
            data = json.loads(raw_body)
            _debug(
                'Parsed status: active=%s site_name=%r subscription_status=%r',
                data.get('active'),
                data.get('site_name'),
                data.get('subscription_status'),
            )
            return data
    except HTTPError as exc:
        body = exc.read().decode(errors='replace') if exc.fp else ''
        logger.warning(
            '[SiteMatrix] HTTP error %s from %s — body: %s',
            exc.code,
            url,
            body,
        )
        _debug('HTTP error %s — fail open (site stays up). Body: %s', exc.code, body)
        return None
    except (URLError, TimeoutError, ConnectionError, OSError) as exc:
        logger.warning('[SiteMatrix] Request failed: %s', exc)
        _debug('Connection error — fail open (site stays up): %s', exc)
        return None
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning('[SiteMatrix] Invalid JSON response: %s', exc)
        _debug('Invalid JSON — fail open (site stays up): %s', exc)
        return None


def get_cached_site_status():
    if settings.DEBUG:
        _debug('DEBUG mode — calling SiteMatrix API on every request (cache skipped).')
        return fetch_site_status()

    cached = cache.get(CACHE_KEY)
    if cached is not None and cached.get('active'):
        _debug(
            'Using cached ACTIVE status (subscription=%r) — no API call this request.',
            cached.get('subscription_status'),
        )
        return cached

    if cached is not None and not cached.get('active'):
        _debug('Site is OFF — skipping cache, calling API again on this request.')

    _debug('Calling SiteMatrix API now.')
    data = fetch_site_status()
    if data is not None and data.get('active'):
        cache.set(CACHE_KEY, data, settings.SITEMATRIX_CACHE_SECONDS)
        _debug('Site active — cached for %ss.', settings.SITEMATRIX_CACHE_SECONDS)
    else:
        cache.delete(CACHE_KEY)
        if data is not None:
            _debug('Site inactive — not cached; every request will re-check API.')
        else:
            _debug('API failed — not cached; next request will retry.')
    return data


def is_site_active(request_path=''):
    if not settings.SITEMATRIX_ENABLED:
        return True

    if request_path:
        _debug('Checking site status for request: %s', request_path)

    data = get_cached_site_status()
    if data is None:
        _debug('No status data — fail open, allowing request.')
        return True

    active = bool(data.get('active'))
    if active:
        _debug('Site is ACTIVE — allowing request.')
    else:
        _debug(
            'Site is INACTIVE (subscription=%r) — blocking with 503. Message: %s',
            data.get('subscription_status'),
            data.get('message'),
        )
    return active


def unavailable_message():
    data = get_cached_site_status() or {}
    return (
        data.get('public_message')
        or data.get('message')
        or 'This website is temporarily unavailable. Please contact support.'
    )


def _reason_from_status(data):
    reason = data.get('reason')
    if reason:
        return reason
    subscription = data.get('subscription_status', '')
    mapping = {
        'past_due': 'payment',
        'cancelled': 'cancelled',
        'paused': 'paused',
        'trial': 'trial',
    }
    return mapping.get(subscription, 'unavailable')


def get_unavailable_context():
    from django.urls import reverse

    data = get_cached_site_status() or {}
    reason = _reason_from_status(data)
    site_name = data.get('site_name') or settings.SITE_NAME
    message = unavailable_message()

    headlines = {
        'payment': 'Temporarily offline',
        'cancelled': 'No longer available',
        'deactivated': 'Temporarily offline',
        'paused': 'Paused',
        'trial': 'Coming soon',
        'unavailable': 'Temporarily unavailable',
    }

    portal_url = getattr(settings, 'SITEMATRIX_PORTAL_URL', '').strip()
    support_url = getattr(settings, 'SITEMATRIX_SUPPORT_URL', '').strip()
    if not support_url:
        support_url = reverse('website:home') + '#contact'

    if reason in ('payment', 'trial') and portal_url:
        owner_action_url = portal_url
        owner_action_label = (
            'Manage billing' if reason == 'payment' else 'Set up subscription'
        )
        owner_hint = (
            'Site owner? Update your payment details to bring this site back online.'
            if reason == 'payment'
            else 'Site owner? Log in and subscribe to publish your website.'
        )
    elif portal_url:
        owner_action_url = portal_url
        owner_action_label = 'Site owner login'
        owner_hint = 'Site owner or visitor? Contact support if you need assistance.'
    else:
        owner_action_url = ''
        owner_action_label = ''
        owner_hint = 'Please contact support if you need assistance.'

    return {
        'website': {'name': site_name},
        'preview': False,
        'reason': reason,
        'headline': headlines.get(reason, headlines['unavailable']),
        'message': message,
        'owner_hint': owner_hint,
        'owner_action_label': owner_action_label,
        'owner_action_url': owner_action_url,
        'support_url': support_url,
    }


def render_unavailable_page():
    from django.template.loader import render_to_string

    return render_to_string('sitematrix/unavailable.html', get_unavailable_context())
