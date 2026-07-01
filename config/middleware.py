"""Site and request middleware."""


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


class SiteMatrixStatusMiddleware:
    """
    Check SiteMatrix whether this client site should stay live.
    Fail open if SiteMatrix is unreachable. Result is cached to limit API calls.
    Static and media requests are always passed through so the offline page can load assets.
    """

    _startup_logged = False

    def __init__(self, get_response):
        self.get_response = get_response

    @staticmethod
    def _is_static_or_media_request(request):
        from django.conf import settings

        path = request.path.lstrip('/')
        static_prefix = settings.STATIC_URL.lstrip('/')
        media_prefix = settings.MEDIA_URL.lstrip('/')
        return path.startswith(static_prefix) or path.startswith(media_prefix)

    def __call__(self, request):
        from django.conf import settings
        from django.http import HttpResponse

        if not SiteMatrixStatusMiddleware._startup_logged:
            from config.sitematrix import log_startup_status
            log_startup_status()
            SiteMatrixStatusMiddleware._startup_logged = True

        if settings.SITEMATRIX_ENABLED and not self._is_static_or_media_request(request):
            from config.sitematrix import is_site_active, render_unavailable_page

            if not is_site_active(request.path):
                return HttpResponse(
                    render_unavailable_page(),
                    status=503,
                    content_type='text/html',
                )

        return self.get_response(request)
