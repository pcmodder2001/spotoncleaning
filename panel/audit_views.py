from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import render

from audit.actions import ACTION_LABELS, CATEGORY_CHOICES
from audit.models import AuditLog
from panel.decorators import sysadmin_required


@sysadmin_required
def audit_log_view(request):
    logs = AuditLog.objects.select_related('user')
    query = request.GET.get('q', '').strip()
    category = request.GET.get('category', '')
    role = request.GET.get('role', '')
    action = request.GET.get('action', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')

    if query:
        logs = logs.filter(
            Q(description__icontains=query)
            | Q(actor_email__icontains=query)
            | Q(actor_name__icontains=query)
            | Q(target_label__icontains=query)
            | Q(target_id__icontains=query)
        )
    if category:
        logs = logs.filter(category=category)
    if role:
        logs = logs.filter(actor_role=role)
    if action:
        logs = logs.filter(action=action)
    if date_from:
        logs = logs.filter(created_at__date__gte=date_from)
    if date_to:
        logs = logs.filter(created_at__date__lte=date_to)

    paginator = Paginator(logs, 50)
    page_obj = paginator.get_page(request.GET.get('page'))

    role_choices = [
        ('standard', 'Standard user'),
        ('engineer', 'Engineer'),
        ('admin', 'Admin'),
        ('sysadmin', 'System admin'),
        ('guest', 'Guest'),
    ]

    return render(request, 'panel/audit/list.html', {
        'page_obj': page_obj,
        'query': query,
        'category_filter': category,
        'role_filter': role,
        'action_filter': action,
        'date_from': date_from,
        'date_to': date_to,
        'category_choices': CATEGORY_CHOICES,
        'role_choices': role_choices,
        'action_choices': sorted(ACTION_LABELS.items(), key=lambda item: item[1]),
    })
