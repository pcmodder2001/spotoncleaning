"""Redirect bare domain to the canonical www host in production."""


class CanonicalHostMiddleware:
    """
    spotonappliancecleaning.co.uk is served as a static homepage via Cloudflare,
    while www.spotonappliancecleaning.co.uk proxies to the Django app. Redirect
    bare-domain requests so email links and bookmarks reach the app.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        from django.conf import settings
        from django.http import HttpResponsePermanentRedirect

        canonical = getattr(settings, 'CANONICAL_HOST', '')
        if not canonical or settings.DEBUG:
            return self.get_response(request)

        host = request.get_host().split(':')[0].lower()
        canonical = canonical.lower()
        bare = canonical.removeprefix('www.')

        if host == bare and host != canonical:
            scheme = 'https' if request.is_secure() else 'http'
            return HttpResponsePermanentRedirect(
                f'{scheme}://{canonical}{request.get_full_path()}'
            )

        return self.get_response(request)
