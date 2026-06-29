"""UK address lookup by postcode (Ideal Postcodes API)."""

import json
import logging
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import urlopen

from django.conf import settings
from django.core.cache import cache

from bookings.routing import is_valid_uk_postcode, normalize_postcode

logger = logging.getLogger(__name__)


def get_address_lookup_api_key():
    key = getattr(settings, 'IDEAL_POSTCODES_API_KEY', '')
    if key:
        return key
    if settings.DEBUG:
        return 'ak_test'
    return ''


def _format_label(entry):
    parts = [entry.get('line_1'), entry.get('line_2'), entry.get('line_3'), entry.get('post_town')]
    return ', '.join(part for part in parts if part)


def _parse_entry(entry):
    return {
        'id': entry.get('id') or str(entry.get('udprn', '')),
        'label': _format_label(entry),
        'line_1': entry.get('line_1', ''),
        'line_2': entry.get('line_2', ''),
        'city': entry.get('post_town', ''),
        'postcode': entry.get('postcode', ''),
    }


def lookup_addresses(postcode):
    normalized = normalize_postcode(postcode)
    if not is_valid_uk_postcode(normalized):
        return {'addresses': [], 'error': 'invalid_postcode', 'postcode': normalized}

    from bookings.service_area import is_postcode_in_service_area

    allowed, area_message = is_postcode_in_service_area(normalized)
    if not allowed:
        return {
            'addresses': [],
            'error': 'outside_service_area',
            'message': area_message,
            'postcode': normalized,
        }

    api_key = get_address_lookup_api_key()
    if not api_key:
        return {
            'addresses': [],
            'error': 'not_configured',
            'manual_entry': True,
            'postcode': normalized,
        }

    cache_key = f'address-lookup:{normalized.replace(" ", "")}'
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    slug = quote(normalized.replace(' ', ''))
    url = (
        f'https://api.ideal-postcodes.co.uk/v1/postcodes/{slug}'
        f'?api_key={quote(api_key)}'
    )
    try:
        with urlopen(url, timeout=8) as response:
            data = json.loads(response.read().decode())
    except HTTPError as exc:
        if exc.code == 404:
            result = {'addresses': [], 'error': 'postcode_not_found', 'postcode': normalized}
            cache.set(cache_key, result, 60 * 60)
            return result
        logger.warning('Address lookup HTTP error for %s: %s', normalized, exc)
        return {'addresses': [], 'error': 'lookup_failed', 'postcode': normalized}
    except (URLError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
        logger.warning('Address lookup failed for %s: %s', normalized, exc)
        return {'addresses': [], 'error': 'lookup_failed', 'postcode': normalized}

    if data.get('code') != 2000:
        error = 'postcode_not_found' if data.get('code') == 4040 else 'lookup_failed'
        result = {'addresses': [], 'error': error, 'postcode': normalized}
        cache.set(cache_key, result, 60 * 60)
        return result

    addresses = [_parse_entry(entry) for entry in data.get('result', [])]
    result = {'addresses': addresses, 'postcode': normalized, 'count': len(addresses)}
    cache.set(cache_key, result, 60 * 60 * 24)
    return result
