from __future__ import annotations

from audit.actions import ACTION_CATEGORIES, ACTION_LABELS
from audit.models import AuditLog


def _client_ip(request):
    if not request:
        return None
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if forwarded:
        return forwarded.split(',')[0].strip() or None
    return request.META.get('REMOTE_ADDR')


def _actor_role(user):
    if not user or not getattr(user, 'is_authenticated', False):
        return 'guest'
    if getattr(user, 'is_sysadmin', False):
        return 'sysadmin'
    return getattr(user, 'role', '') or 'standard'


def log_action(
    action: str,
    description: str,
    *,
    request=None,
    user=None,
    actor_email: str = '',
    actor_name: str = '',
    target_type: str = '',
    target_id: str = '',
    target_label: str = '',
    metadata=None,
):
    """Record an auditable action. Never raises — logging must not break the app."""
    try:
        if user is None and request is not None and getattr(request, 'user', None):
            if request.user.is_authenticated:
                user = request.user

        if user and user.is_authenticated:
            actor_email = actor_email or user.email
            actor_name = actor_name or user.full_name
        elif actor_email and not actor_name:
            actor_name = actor_email

        AuditLog.objects.create(
            action=action,
            category=ACTION_CATEGORIES.get(action, 'admin'),
            description=description[:2000],
            user=user if user and user.is_authenticated else None,
            actor_email=actor_email[:254],
            actor_name=actor_name[:200],
            actor_role=_actor_role(user),
            target_type=target_type[:64],
            target_id=str(target_id)[:64] if target_id else '',
            target_label=target_label[:255],
            metadata=metadata or {},
            ip_address=_client_ip(request),
        )
    except Exception:
        import logging
        logging.getLogger(__name__).exception('Failed to write audit log for action %s', action)


def action_label(action_code: str) -> str:
    return ACTION_LABELS.get(action_code, action_code)
