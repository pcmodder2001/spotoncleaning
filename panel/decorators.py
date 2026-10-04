from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.shortcuts import redirect


def _can_access_panel(user):
    return user.is_authenticated and user.can_access_panel


def _can_manage_site(user):
    return user.is_authenticated and user.can_manage_site


def panel_required(view_func):
    """Engineer, admin, or system administrator."""
    decorated = user_passes_test(_can_access_panel, login_url='accounts:login')(view_func)
    decorated.__panel_role__ = 'panel'
    return decorated


def admin_required(view_func):
    """Site admin or system administrator — full panel management."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        if not request.user.can_manage_site:
            messages.error(request, 'You do not have permission to access that page.')
            return redirect('panel:dashboard')
        return view_func(request, *args, **kwargs)

    wrapper.__panel_role__ = 'admin'
    return wrapper


def sysadmin_required(view_func):
    @wraps(view_func)
    @panel_required
    def wrapper(request, *args, **kwargs):
        if not request.user.is_sysadmin:
            messages.error(request, 'That page is restricted to system administrators.')
            return redirect('panel:dashboard')
        return view_func(request, *args, **kwargs)

    wrapper.__panel_role__ = 'sysadmin'
    return wrapper


def ops_required(view_func):
    """Engineer or system administrator — schedule / HR. Normal site admins excluded."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        if not request.user.can_access_ops_tools:
            messages.error(request, 'You do not have permission to access that page.')
            return redirect('panel:dashboard')
        return view_func(request, *args, **kwargs)

    wrapper.__panel_role__ = 'ops'
    return wrapper


# Backwards compatibility for existing imports.
staff_required = panel_required
