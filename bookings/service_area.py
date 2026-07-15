"""Restrict bookings to enabled coverage areas."""

from django.conf import settings

from bookings.coverage import (
    EXCLUDED_OUTWARD_CODES,
    get_enabled_coverage_areas,
    invalidate_coverage_cache,
    outward_code,
    postcode_is_covered,
)
from bookings.routing import fetch_postcode_info, normalize_postcode


def service_area_name():
    return getattr(settings, 'SERVICE_AREA_NAME', settings.SITE_LOCAL_AREA)


def service_area_enforced():
    return getattr(settings, 'SERVICE_AREA_ENFORCED', True)


def service_area_error_message():
    return (
        f'Sorry — we currently only cover selected areas around {service_area_name()}. '
        'Please enter a postcode within our service area.'
    )


def no_coverage_error_message():
    return (
        'We are not currently accepting online bookings — please contact us directly.'
    )


def is_postcode_in_service_area(postcode):
    """Return (allowed, error_message). error_message is empty when allowed."""
    # UK-wide booking: only validate postcode format until location-specific
    # coverage is rebuilt. Uncomment the block below to restore area restrictions.
    normalized = normalize_postcode(postcode)
    if not normalized:
        return False, 'Please enter a valid UK postcode.'
    return True, ''

    # --- Location restrictions (disabled) ---
    # if not service_area_enforced():
    #     return True, ''
    #
    # normalized = normalize_postcode(postcode)
    # if not normalized:
    #     return False, service_area_error_message()
    #
    # outward = outward_code(normalized)
    # if outward in EXCLUDED_OUTWARD_CODES:
    #     return False, service_area_error_message()
    #
    # info = fetch_postcode_info(normalized)
    # if not postcode_is_covered(normalized, info):
    #     if not get_enabled_coverage_areas():
    #         return False, no_coverage_error_message()
    #     return False, service_area_error_message()
    #
    # return True, ''


def postcode_service_area_error(postcode):
    allowed, message = is_postcode_in_service_area(postcode)
    return None if allowed else message


__all__ = [
    'EXCLUDED_OUTWARD_CODES',
    'invalidate_coverage_cache',
    'is_postcode_in_service_area',
    'outward_code',
    'postcode_service_area_error',
    'service_area_enforced',
    'service_area_error_message',
    'service_area_name',
]
