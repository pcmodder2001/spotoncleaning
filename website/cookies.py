COOKIE_CONSENT_NAME = 'spoton_cookie_consent'
CONSENT_ESSENTIAL = 'essential'
CONSENT_MARKETING = 'marketing'
CONSENT_MAX_AGE_SECONDS = 365 * 24 * 60 * 60


def get_cookie_consent(request):
    return (request.COOKIES.get(COOKIE_CONSENT_NAME) or '').strip()


def has_marketing_consent(request):
    return get_cookie_consent(request) == CONSENT_MARKETING


def is_public_site_path(request):
    path = getattr(request, 'path', '') or ''
    return not path.startswith('/panel/')


def show_cookie_banner(request):
    if not is_public_site_path(request):
        return False
    return not get_cookie_consent(request)
