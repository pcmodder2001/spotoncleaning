import csv
import json
from datetime import datetime, timedelta

from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from bookings.checklist import checklist_from_post, merge_checklist
from bookings.models import Availability, BlockedDate, Booking, BookingPhoto, BookingStatus, TimeSlot
from bookings.notifications import send_booking_status_email, send_followup_registered_email_for_booking
from bookings.scheduling import get_day_schedule_panel_data, get_week_schedule_summary
from bookings.utils import cancel_booking
from audit.actions import (
    BOOKING_BULK_CANCEL,
    BOOKING_BULK_CONFIRM,
    BOOKING_BULK_EXPORT,
    BOOKING_BULK_FOLLOWUP_EMAIL,
    BOOKING_PHOTO_DELETED,
    AVAILABILITY_UPDATED,
)
from audit.services import log_action
from panel.decorators import admin_required, ops_required, sysadmin_required


def _parse_date(value, default=None):
    if not value:
        return default
    try:
        return datetime.strptime(value, '%Y-%m-%d').date()
    except ValueError:
        return default


def _week_start(date):
    return date - timedelta(days=date.weekday())


@ops_required
def schedule_view(request):
    today = timezone.localdate()
    selected_date = _parse_date(request.GET.get('date'), today)
    week_start = _parse_date(request.GET.get('week'), _week_start(selected_date))

    prev_day = selected_date - timedelta(days=1)
    next_day = selected_date + timedelta(days=1)
    prev_week = week_start - timedelta(days=7)
    next_week = week_start + timedelta(days=7)

    return render(request, 'panel/schedule/day.html', {
        'selected_date': selected_date,
        'week_start': week_start,
        'week_days': get_week_schedule_summary(week_start),
        'prev_day': prev_day,
        'next_day': next_day,
        'prev_week': prev_week,
        'next_week': next_week,
        'today': today,
    })


@ops_required
@require_GET
def schedule_api_view(request):
    selected_date = _parse_date(request.GET.get('date'), timezone.localdate())
    data = get_day_schedule_panel_data(selected_date)
    return JsonResponse(data)


@admin_required
@require_POST
def booking_bulk_action_view(request):
    action = request.POST.get('bulk_action', '')
    booking_ids = request.POST.getlist('booking_ids')

    if not booking_ids:
        messages.error(request, 'Select at least one booking.')
        return redirect('panel:booking_list')

    bookings = Booking.objects.filter(pk__in=booking_ids)
    count = bookings.count()

    if action == 'confirm':
        pending_bookings = list(
            bookings.filter(status=BookingStatus.PENDING).select_related('time_slot')
        )
        updated = len(pending_bookings)
        if updated:
            Booking.objects.filter(
                pk__in=[booking.pk for booking in pending_bookings],
            ).update(status=BookingStatus.CONFIRMED)
            for booking in pending_bookings:
                booking.status = BookingStatus.CONFIRMED
                send_booking_status_email(booking)
        log_action(
            BOOKING_BULK_CONFIRM,
            f'Confirmed {updated} booking(s).',
            request=request,
            target_type='booking',
            target_label=f'{updated} bookings',
            metadata={'booking_ids': booking_ids, 'count': updated},
        )
        if updated:
            messages.success(request, f'{updated} pending booking(s) confirmed.')
        else:
            messages.info(request, 'No pending bookings were selected to confirm.')
    elif action == 'cancel':
        cancelled = 0
        cancelled_ids = []
        for booking in bookings:
            if cancel_booking(booking):
                cancelled += 1
                cancelled_ids.append(booking.pk)
        log_action(
            BOOKING_BULK_CANCEL,
            f'Bulk cancelled {cancelled} booking(s).',
            request=request,
            target_type='booking',
            target_label=f'{cancelled} bookings',
            metadata={'booking_ids': cancelled_ids, 'count': cancelled},
        )
        messages.success(request, f'{cancelled} booking(s) cancelled.')
    elif action == 'export':
        log_action(
            BOOKING_BULK_EXPORT,
            f'Exported {count} booking(s) to CSV.',
            request=request,
            target_type='booking',
            target_label=f'{count} bookings',
            metadata={'booking_ids': booking_ids, 'count': count},
        )
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="bookings.csv"'
        writer = csv.writer(response)
        writer.writerow([
            'ID', 'Customer', 'Email', 'Phone', 'Services', 'Date', 'Time',
            'Address', 'Postcode', 'Status', 'Total', 'Discount',
        ])
        for booking in bookings.select_related('time_slot', 'user').prefetch_related('services'):
            writer.writerow([
                booking.pk,
                booking.contact_full_name,
                booking.contact_email,
                booking.contact_phone,
                booking.service_summary,
                booking.date.isoformat(),
                booking.time_slot.time.strftime('%H:%M'),
                booking.full_address(),
                booking.postcode,
                booking.status,
                booking.total_price,
                booking.discount_amount,
            ])
        return response
    elif action == 'send_followup_emails':
        if not request.user.is_sysadmin:
            messages.error(request, 'Only system administrators can send follow-up emails.')
            return redirect(request.POST.get('next') or 'panel:booking_list')

        sent = 0
        skipped = 0
        failed = 0
        sent_ids = []
        for booking in bookings.select_related('user'):
            email = (booking.contact_email or '').strip()
            if not email:
                skipped += 1
                continue
            if send_followup_registered_email_for_booking(booking):
                sent += 1
                sent_ids.append(booking.pk)
            else:
                failed += 1
        log_action(
            BOOKING_BULK_FOLLOWUP_EMAIL,
            f'Sent follow-up confirmation emails for {sent} booking(s).',
            request=request,
            target_type='booking',
            target_label=f'{sent} bookings',
            metadata={
                'booking_ids': sent_ids,
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
    else:
        messages.error(request, 'Unknown bulk action.')

    return redirect(request.POST.get('next') or 'panel:booking_list')


@admin_required
@require_POST
def booking_photo_delete_view(request, pk, photo_pk):
    booking = get_object_or_404(Booking, pk=pk)
    photo = get_object_or_404(BookingPhoto, pk=photo_pk, booking=booking)
    photo_type = photo.photo_type
    photo_label = photo.get_photo_type_display().lower()
    photo.image.delete(save=False)
    photo.delete()
    log_action(
        BOOKING_PHOTO_DELETED,
        f'Deleted {photo_label} photo for booking #{booking.pk}.',
        request=request,
        target_type='booking',
        target_id=booking.pk,
        target_label=f'Booking #{booking.pk}',
        metadata={'photo_id': photo_pk, 'photo_type': photo_type},
    )
    messages.success(request, 'Photo removed.')
    return redirect('panel:booking_edit', pk=pk)


@sysadmin_required
@require_POST
def availability_quick_action_view(request):
    action = request.POST.get('action')
    performed = False

    if action == 'block_day_full':
        date_str = request.POST.get('date')
        reason = request.POST.get('reason', 'Fully booked')
        date_obj = _parse_date(date_str)
        if not date_obj:
            messages.error(request, 'Choose a valid date.')
        else:
            BlockedDate.objects.update_or_create(
                date=date_obj,
                defaults={
                    'reason': reason,
                    'closure_type': BlockedDate.ClosureType.FULL,
                },
            )
            messages.success(request, f'{date_obj.strftime("%d %b %Y")} marked as fully booked.')
            performed = True
    elif action == 'duplicate_week':
        source_start = _parse_date(request.POST.get('source_week_start'))
        if not source_start:
            messages.error(request, 'Choose a valid week start date (Monday).')
        else:
            source_start = _week_start(source_start)
            target_start = source_start + timedelta(days=7)
            copied_blocks = 0
            copied_slots = 0
            for offset in range(7):
                source_date = source_start + timedelta(days=offset)
                target_date = target_start + timedelta(days=offset)
                if BlockedDate.objects.filter(date=source_date).exists():
                    source_block = BlockedDate.objects.get(date=source_date)
                    _, created = BlockedDate.objects.update_or_create(
                        date=target_date,
                        defaults={
                            'reason': source_block.reason or 'Copied from previous week',
                            'closure_type': source_block.closure_type,
                        },
                    )
                    if created:
                        copied_blocks += 1
                for avail in Availability.objects.filter(date=source_date):
                    Availability.objects.update_or_create(
                        date=target_date,
                        time_slot=avail.time_slot,
                        defaults={'available': avail.available},
                    )
                    copied_slots += 1
            messages.success(
                request,
                f'Copied {copied_blocks} blocked day(s) and {copied_slots} slot override(s) to the following week.',
            )
            performed = True
    else:
        messages.error(request, 'Unknown action.')
        return redirect('panel:availability')

    if performed:
        log_action(
            AVAILABILITY_UPDATED,
            f'Availability quick action: {action}.',
            request=request,
            target_type='availability',
            metadata={'action': action},
        )

    return redirect('panel:availability')
