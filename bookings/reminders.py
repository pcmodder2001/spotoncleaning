"""Day-before booking reminder emails and SMS."""

from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from audit.actions import BOOKING_REMINDER_SENT
from audit.services import log_action
from bookings.models import Booking, BookingStatus
from bookings.sms import send_sms_message, sms_is_configured

REMINDER_ELIGIBLE_STATUSES = (
    BookingStatus.PENDING,
    BookingStatus.CONFIRMED,
)


def get_reminder_target_date(for_date=None):
    """Bookings on this date get reminded the day before."""
    if for_date is None:
        for_date = timezone.localdate() + timedelta(days=1)
    return for_date


def bookings_due_for_reminder(for_date=None, *, include_sent=False):
    target_date = get_reminder_target_date(for_date)
    queryset = (
        Booking.objects.filter(
            date=target_date,
            status__in=REMINDER_ELIGIBLE_STATUSES,
        )
        .select_related('time_slot', 'user')
        .prefetch_related('services')
        .order_by('time_slot__time', 'pk')
    )
    if not include_sent:
        queryset = queryset.filter(reminder_sent_at__isnull=True)
    return queryset


def get_booking_reminder_context(booking):
    from bookings.notifications import get_booking_email_context

    window = booking.appointment_time_window()
    services = list(booking.get_services())
    return {
        **get_booking_email_context(booking),
        'time_window': booking.appointment_time_window_display,
        'time_window_end': window['end'],
        'duration_minutes': window['duration_minutes'],
        'services_list': [service.name for service in services],
        'access_notes': booking.customer_access_notes,
    }


def build_reminder_sms_text(booking):
    window = booking.appointment_time_window()
    start = window['start'].strftime('%H:%M')
    end = window['end'].strftime('%H:%M')
    date_label = booking.date.strftime('%a %d %b')
    services = booking.service_summary
    address = booking.full_address()

    lines = [
        f'{settings.SITE_NAME}: Reminder — your clean is tomorrow {date_label}, {start}–{end}.',
        address + '.',
        f'Booked: {services}.',
    ]
    if booking.customer_access_notes:
        notes = booking.customer_access_notes
        if len(notes) > 80:
            notes = notes[:77] + '...'
        lines.append(f'Notes: {notes}')

    if settings.SITE_PHONE:
        lines.append(f'Questions? {settings.SITE_PHONE}')

    return ' '.join(lines)


def send_booking_reminder(booking, *, request=None, force=False):
    """
    Send day-before reminder via email and optional SMS.
    Returns dict with channel results.
    """
    if not getattr(settings, 'BOOKING_REMINDERS_ENABLED', True):
        return {'skipped': True, 'reason': 'reminders disabled'}

    if booking.status not in REMINDER_ELIGIBLE_STATUSES:
        return {'skipped': True, 'reason': f'status is {booking.status}'}

    if booking.reminder_sent_at and not force:
        return {'skipped': True, 'reason': 'already sent'}

    results = {
        'email': None,
        'sms': None,
        'marked_sent': False,
    }

    email = (booking.contact_email or '').strip()
    if email:
        from bookings.notifications import send_booking_reminder_email

        results['email'] = send_booking_reminder_email(booking)
    else:
        results['email'] = False

    phone = (booking.contact_phone or '').strip()
    if phone and getattr(settings, 'SMS_ENABLED', False):
        sms_ok, sms_detail = send_sms_message(phone, build_reminder_sms_text(booking))
        results['sms'] = sms_ok
        results['sms_detail'] = sms_detail
    elif phone and sms_is_configured() is False:
        results['sms'] = None
    elif phone:
        results['sms'] = False
        results['sms_detail'] = 'SMS not configured'

    email_ok = results['email'] is True
    sms_ok = results['sms'] is True
    if email_ok or sms_ok:
        booking.reminder_sent_at = timezone.now()
        booking.save(update_fields=['reminder_sent_at', 'updated_at'])
        results['marked_sent'] = True

        channels = []
        if email_ok:
            channels.append('email')
        if sms_ok:
            channels.append('sms')

        log_action(
            BOOKING_REMINDER_SENT,
            (
                f'Sent day-before reminder for booking #{booking.pk} '
                f'({booking.date}, {booking.contact_full_name}) via {", ".join(channels)}.'
            ),
            request=request,
            target_type='booking',
            target_id=booking.pk,
            target_label=f'Booking #{booking.pk} — {booking.contact_full_name}',
            metadata={
                'channels': channels,
                'appointment_date': booking.date.isoformat(),
            },
        )

    return results
