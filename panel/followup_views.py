from datetime import timedelta

from django.contrib import messages
from django.db.models import Case, IntegerField, Value, When
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from audit.actions import FOLLOWUP_CREATED, FOLLOWUP_DELETED, FOLLOWUP_UPDATED
from audit.services import log_action
from bookings.models import CustomerFollowUp
from panel.decorators import admin_required


@admin_required
def followup_list_view(request):
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'add':
            name = request.POST.get('name', '').strip()
            phone = request.POST.get('phone', '').strip()
            email = request.POST.get('email', '').strip()
            notes = request.POST.get('notes', '').strip()
            interval_raw = request.POST.get('interval_months', '').strip()

            try:
                interval_months = int(interval_raw)
            except (TypeError, ValueError):
                interval_months = None

            valid_intervals = {choice.value for choice in CustomerFollowUp.IntervalMonths}
            if not name:
                messages.error(request, 'Enter the customer name.')
            elif interval_months not in valid_intervals:
                messages.error(request, 'Choose when to come back (3, 6, 9, or 12 months).')
            elif not phone and not email:
                messages.error(request, 'Enter a phone number or email address.')
            else:
                due_date = CustomerFollowUp.due_date_from_interval(interval_months)
                followup = CustomerFollowUp.objects.create(
                    name=name,
                    phone=phone,
                    email=email,
                    notes=notes,
                    interval_months=interval_months,
                    due_date=due_date,
                )
                log_action(
                    FOLLOWUP_CREATED,
                    f'Added follow-up for {followup.name} due {followup.due_date}.',
                    request=request,
                    target_type='followup',
                    target_id=followup.pk,
                    target_label=followup.name,
                    metadata={
                        'interval_months': followup.interval_months,
                        'due_date': followup.due_date.isoformat(),
                    },
                )
                messages.success(
                    request,
                    f'{followup.name} added — come back {followup.get_interval_months_display()} '
                    f'(due {followup.due_date.strftime("%d %b %Y")}).',
                )
        elif action == 'done':
            followup = get_object_or_404(CustomerFollowUp, pk=request.POST.get('followup_id'))
            is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
            if not followup.can_mark_done:
                message = (
                    f'{followup.name} cannot be marked done until '
                    f'{followup.due_date.strftime("%d %b %Y")}.'
                )
                if is_ajax:
                    return JsonResponse({'success': False, 'error': message}, status=400)
                messages.error(request, message)
            else:
                followup.status = CustomerFollowUp.Status.DONE
                followup.completed_at = timezone.now()
                followup.save(update_fields=['status', 'completed_at', 'updated_at'])
                log_action(
                    FOLLOWUP_UPDATED,
                    f'Marked follow-up for {followup.name} as done.',
                    request=request,
                    target_type='followup',
                    target_id=followup.pk,
                    target_label=followup.name,
                )
                if is_ajax:
                    return JsonResponse({
                        'success': True,
                        'name': followup.name,
                        'phone': followup.phone,
                        'email': followup.email,
                        'notes': followup.notes,
                        'interval_months': followup.interval_months,
                    })
                messages.success(request, f'{followup.name} marked as done.')
        elif action == 'reopen':
            followup = get_object_or_404(CustomerFollowUp, pk=request.POST.get('followup_id'))
            followup.status = CustomerFollowUp.Status.OPEN
            followup.completed_at = None
            followup.save(update_fields=['status', 'completed_at', 'updated_at'])
            log_action(
                FOLLOWUP_UPDATED,
                f'Reopened follow-up for {followup.name}.',
                request=request,
                target_type='followup',
                target_id=followup.pk,
                target_label=followup.name,
            )
            messages.success(request, f'{followup.name} reopened.')
        elif action == 'delete':
            followup = get_object_or_404(CustomerFollowUp, pk=request.POST.get('followup_id'))
            name = followup.name
            followup_id = followup.pk
            followup.delete()
            log_action(
                FOLLOWUP_DELETED,
                f'Deleted follow-up for {name}.',
                request=request,
                target_type='followup',
                target_id=followup_id,
                target_label=name,
            )
            messages.success(request, f'Follow-up for {name} deleted.')
        return redirect('panel:followup_list')

    show = request.GET.get('show', 'open')
    today = timezone.localdate()
    queryset = CustomerFollowUp.objects.all()

    if show == 'done':
        queryset = queryset.filter(status=CustomerFollowUp.Status.DONE)
    elif show == 'all':
        queryset = queryset.exclude(status=CustomerFollowUp.Status.CANCELLED)
    else:
        show = 'open'
        queryset = queryset.filter(status=CustomerFollowUp.Status.OPEN)

    followups = queryset.annotate(
        urgency=Case(
            When(status=CustomerFollowUp.Status.OPEN, due_date__lt=today, then=Value(0)),
            When(status=CustomerFollowUp.Status.OPEN, due_date__lte=today, then=Value(1)),
            When(status=CustomerFollowUp.Status.OPEN, then=Value(2)),
            default=Value(3),
            output_field=IntegerField(),
        )
    ).order_by('urgency', 'due_date', 'name')

    open_count = CustomerFollowUp.objects.filter(status=CustomerFollowUp.Status.OPEN).count()
    overdue_count = CustomerFollowUp.objects.filter(
        status=CustomerFollowUp.Status.OPEN,
        due_date__lt=today,
    ).count()
    due_soon_count = CustomerFollowUp.objects.filter(
        status=CustomerFollowUp.Status.OPEN,
        due_date__gte=today,
        due_date__lte=today + timedelta(days=14),
    ).count()

    return render(request, 'panel/followups/list.html', {
        'followups': followups,
        'show': show,
        'today': today,
        'open_count': open_count,
        'overdue_count': overdue_count,
        'due_soon_count': due_soon_count,
        'interval_choices': CustomerFollowUp.IntervalMonths.choices,
    })
