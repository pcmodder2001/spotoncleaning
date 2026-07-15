"""Restrict bookings to editable service boundary polygons."""

from django.conf import settings

from bookings.coverage import (
    get_editable_coverage_boundaries,
    point_in_any_boundary,
)
from bookings.routing import fetch_postcode_info, normalize_postcode


def service_area_name():
    return getattr(settings, 'SERVICE_AREA_NAME', settings.SITE_LOCAL_AREA)


def service_area_enforced():
    return getattr(settings, 'SERVICE_AREA_ENFORCED', True)


def service_area_error_message():
    return (
        'Sorry — we do not currently cover your postcode. '
        'Please check you are within one of our service areas on the map.'
    )


def no_coverage_error_message():
    return (
        'We are not currently accepting online bookings in your area — please contact us directly.'
    )


def postcode_lookup_error_message():
    return 'We could not verify that postcode. Please check it and try again.'


def is_postcode_in_service_area(postcode):
    """Return (allowed, error_message). error_message is empty when allowed."""
    if not service_area_enforced():
        return True, ''

    normalized = normalize_postcode(postcode)
    if not normalized:
        return False, 'Please enter a valid UK postcode.'

    boundaries = get_editable_coverage_boundaries()
    if not boundaries:
        return False, no_coverage_error_message()

    info = fetch_postcode_info(normalized)
    if not info or info.get('latitude') is None or info.get('longitude') is None:
        return False, postcode_lookup_error_message()

    if point_in_any_boundary(float(info['latitude']), float(info['longitude'])):
        return True, ''

    return False, service_area_error_message()

    # --- Old postcode-district restrictions (replaced by map boundaries) ---
    # from bookings.coverage import (
    #     EXCLUDED_OUTWARD_CODES,
    #     get_enabled_coverage_areas,
    #     outward_code,
    #     postcode_is_covered,
    # )
    # outward = outward_code(normalized)
    # if outward in EXCLUDED_OUTWARD_CODES:
    #     return False, service_area_error_message()
    # if not postcode_is_covered(normalized, info):
    #     if not get_enabled_coverage_areas():
    #         return False, no_coverage_error_message()
    #     return False, service_area_error_message()


def postcode_service_area_error(postcode):
    allowed, message = is_postcode_in_service_area(postcode)
    return None if allowed else message


__all__ = [
    'is_postcode_in_service_area',
    'no_coverage_error_message',
    'postcode_service_area_error',
    'service_area_enforced',
    'service_area_error_message',
    'service_area_name',
]
