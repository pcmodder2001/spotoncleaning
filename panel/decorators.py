from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.shortcuts import redirect


def staff_required(view_func):
    return user_passes_test(lambda u: u.is_authenticated and u.is_staff)(view_func)


def sysadmin_required(view_func):
    @wraps(view_func)
    @staff_required
    def wrapper(request, *args, **kwargs):
        if not request.user.is_sysadmin:
            messages.error(request, 'That page is restricted to system administrators.')
            return redirect('panel:dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper
