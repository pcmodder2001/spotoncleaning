from django.conf import settings


def site_settings(request):
    return {
        'SITE_NAME': settings.SITE_NAME,
        'SITE_TAGLINE': settings.SITE_TAGLINE,
        'SITE_PHONE': settings.SITE_PHONE,
        'SITE_EMAIL': settings.SITE_EMAIL,
        'SITE_ADDRESS': settings.SITE_ADDRESS,
    }
