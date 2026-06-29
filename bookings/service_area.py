"""Restrict bookings to the configured service area (default: West Yorkshire)."""

import re

from django.conf import settings

from bookings.routing import fetch_postcode_info, normalize_postcode

# Metropolitan boroughs in West Yorkshire
WEST_YORKSHIRE_ADMIN_DISTRICTS = frozenset({
    'Leeds',
    'Bradford',
    'Kirklees',
    'Calderdale',
    'Wakefield',
})

# Outward codes outside West Yorkshire that share a prefix (e.g. BD → Skipton)
EXCLUDED_OUTWARD_CODES = frozenset({
    'BD23',
    'BD24',
})

WEST_YORKSHIRE_OUTWARD_PREFIXES = frozenset({
    'LS',
    'WF',
    'HD',
    'HX',
    'BD',
})


def service_area_name():
    return getattr(settings, 'SERVICE_AREA_NAME', settings.SITE_LOCAL_AREA)


def service_area_enforced():
    return getattr(settings, 'SERVICE_AREA_ENFORCED', True)


def outward_code(postcode):
    normalized = normalize_postcode(postcode)
    if not normalized:
        return ''
    return normalized.split()[0].upper()


def service_area_error_message():
    return (
        f'Sorry — we currently only cover addresses in {service_area_name()}. '
        'Please enter a postcode within our service area.'
    )


def is_postcode_in_service_area(postcode):
    """Return (allowed, error_message). error_message is empty when allowed."""
    if not service_area_enforced():
        return True, ''

    if not normalize_postcode(postcode):
        return False, service_area_error_message()

    outward = outward_code(postcode)
    if outward in EXCLUDED_OUTWARD_CODES:
        return False, service_area_error_message()

    info = fetch_postcode_info(postcode)
    if info:
        district = info.get('admin_district') or ''
        county = (info.get('admin_county') or '').strip().lower()
        if district in WEST_YORKSHIRE_ADMIN_DISTRICTS:
            return True, ''
        if county == 'west yorkshire':
            return True, ''
        return False, service_area_error_message()

    prefix_match = re.match(r'^([A-Z]+)', outward)
    prefix = prefix_match.group(1) if prefix_match else ''
    if prefix in WEST_YORKSHIRE_OUTWARD_PREFIXES and outward not in EXCLUDED_OUTWARD_CODES:
        return True, ''

    return False, service_area_error_message()


def postcode_service_area_error(postcode):
    allowed, message = is_postcode_in_service_area(postcode)
    return None if allowed else message
