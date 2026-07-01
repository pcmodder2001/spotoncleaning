from django.conf import settings

from website.tracking import meta_pixel_enabled, pop_meta_pixel_events


def site_settings(request):
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
        'SITE_DEFAULT_SEO_TITLE': settings.SITE_DEFAULT_SEO_TITLE,
        'META_PIXEL_ID': settings.META_PIXEL_ID if pixel_active else '',
        'meta_pixel_events': pop_meta_pixel_events(request) if pixel_active else [],
    }
