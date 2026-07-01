from datetime import datetime, timedelta

from django.conf import settings


def build_booking_ics(booking):
    """Return iCalendar text for a booking appointment."""
    start = datetime.combine(booking.date, booking.time_slot.time)
    duration = booking.estimated_duration_minutes or 60
    end = start + timedelta(minutes=duration)

    def fmt_local(dt):
        return dt.strftime('%Y%m%dT%H%M%S')

    site = getattr(settings, 'SITE_NAME', 'Spot On Cleaning')
    domain = getattr(settings, 'SITE_DOMAIN', 'spoton-cleaning.local')
    uid = f'booking-{booking.pk}@{domain}'
    location = ', '.join(
        part for part in (
            booking.address_line_1,
            booking.city,
            booking.postcode,
        ) if part
    )
    summary = f'{booking.service_summary} — {site}'
    description = (
        f'Booking reference #{booking.pk}. '
        f'We will review your appointment and confirm by email.'
    )

    lines = [
        'BEGIN:VCALENDAR',
        'VERSION:2.0',
        'PRODID:-//Spot On Cleaning//Booking//EN',
        'CALSCALE:GREGORIAN',
        'METHOD:PUBLISH',
        'BEGIN:VEVENT',
        f'UID:{uid}',
        f'DTSTAMP:{fmt_local(datetime.utcnow())}',
        f'DTSTART:{fmt_local(start)}',
        f'DTEND:{fmt_local(end)}',
        f'SUMMARY:{_escape_ics(summary)}',
        f'DESCRIPTION:{_escape_ics(description)}',
        f'LOCATION:{_escape_ics(location)}',
        'END:VEVENT',
        'END:VCALENDAR',
    ]
    return '\r\n'.join(lines) + '\r\n'


def _escape_ics(value):
    return (value or '').replace('\\', '\\\\').replace(',', '\\,').replace(';', '\\;').replace('\n', '\\n')
