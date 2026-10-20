from datetime import timedelta

from django.contrib import messages
from django.db.models import Case, IntegerField, Value, When
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from audit.actions import FOLLOWUP_BULK_EMAIL, FOLLOWUP_CREATED, FOLLOWUP_DELETED, FOLLOWUP_UPDATED
from audit.services import log_action
from bookings.models import CustomerFollowUp
from bookings.notifications import send_followup_registered_email
from panel.decorators import admin_required


def _followup_list_redirect(request):
    show = request.POST.get('show') or request.GET.get('show') or 'open'
    url = reverse('panel:followup_list')
    if show in ('done', 'all'):
        return redirect(f'{url}?show={show}')
    return redirect(url)


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
                success_msg = (
                    f'{followup.name} added — come back {followup.get_interval_months_display()} '
                    f'(due {followup.due_date.strftime("%d %b %Y")}).'
                )
                if followup.email:
                    if send_followup_registered_email(followup):
                        success_msg += ' Confirmation email sent.'
                    else:
                        messages.warning(
                            request,
                            'Follow-up saved, but the confirmation email could not be sent.',
                        )
                messages.success(request, success_msg)
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
        elif action == 'send_emails':
            if not request.user.is_sysadmin:
                messages.error(request, 'Only system administrators can send follow-up emails.')
                return _followup_list_redirect(request)

            followup_ids = request.POST.getlist('followup_ids')
            if not followup_ids:
                messages.error(request, 'Select at least one follow-up.')
                return _followup_list_redirect(request)

            selected = CustomerFollowUp.objects.filter(pk__in=followup_ids)
            sent = 0
            skipped = 0
            failed = 0
            sent_ids = []
            for followup in selected:
                if not (followup.email or '').strip():
                    skipped += 1
                    continue
                if send_followup_registered_email(followup):
                    sent += 1
                    sent_ids.append(followup.pk)
                else:
                    failed += 1
            log_action(
                FOLLOWUP_BULK_EMAIL,
                f'Sent follow-up confirmation emails for {sent} follow-up(s).',
                request=request,
                target_type='followup',
                target_label=f'{sent} follow-ups',
                metadata={
                    'followup_ids': sent_ids,
                    'sent': sent,
                    'skipped': skipped,
                    'failed': failed,
                },
            )
            parts = []
            if sent:
                parts.append(f'Sent {sent} follow-up email(s).')
            if skipped:
                parts.append(f'{skipped} had no email address.')
            if failed:
                parts.append(f'{failed} failed to send.')
            if not parts:
                messages.info(request, 'No follow-up emails were sent.')
            elif failed:
                messages.warning(request, ' '.join(parts))
            else:
                messages.success(request, ' '.join(parts))
        return _followup_list_redirect(request)

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
