from django.conf import settings

from website.cookies import (
    get_cookie_consent,
    has_marketing_consent,
    is_public_site_path,
    show_cookie_banner,
)
from website.tracking import meta_pixel_enabled, pop_meta_pixel_events


def site_settings(request):
    pixel_configured = bool(getattr(settings, 'META_PIXEL_ID', '').strip())
    pixel_active = meta_pixel_enabled(request)
    return {
        'SITE_NAME': settings.SITE_NAME,
        'SITE_TAGLINE': settings.SITE_TAGLINE,
        'SITE_PHONE': settings.SITE_PHONE,
        'SITE_EMAIL': settings.SITE_EMAIL,
        'SITE_ADDRESS': settings.SITE_ADDRESS,
        'SITE_URL': settings.SITE_URL,
        'SITE_DESCRIPTION': settings.SITE_DESCRIPTION,
        'SITE_KEYWORDS': settings.SITE_KEYWORDS,
        'SITE_LOCAL_AREA': settings.SITE_LOCAL_AREA,
        'LEGAL_LAST_UPDATED': settings.LEGAL_LAST_UPDATED,
        'SITE_DEFAULT_SEO_TITLE': settings.SITE_DEFAULT_SEO_TITLE,
        'META_PIXEL_ID': settings.META_PIXEL_ID if pixel_active else '',
        'meta_pixel_events': pop_meta_pixel_events(request) if pixel_active else [],
        'meta_pixel_configured': pixel_configured and is_public_site_path(request),
        'show_cookie_banner': show_cookie_banner(request),
        'cookie_consent_value': get_cookie_consent(request),
        'cookie_consent_marketing': has_marketing_consent(request),
        'public_site': is_public_site_path(request),
    }
