from django.shortcuts import render


def page_not_found(request, exception=None):
    return render(request, '404.html', status=404)


def server_error(request):
    return render(request, '500.html', status=500)


def permission_denied(request, exception=None):
    return render(request, '403.html', status=403)


def bad_request(request, exception=None):
    return render(request, '400.html', status=400)


def preview_not_found(request):
    return page_not_found(request, exception=None)


def preview_server_error(request):
    return server_error(request)


def preview_permission_denied(request):
    return permission_denied(request, exception=None)


def preview_bad_request(request):
    return bad_request(request, exception=None)
