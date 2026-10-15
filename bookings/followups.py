from django.utils import timezone

from bookings.models import BookingStatus, CustomerFollowUp


def followup_note_for_booking(booking):
    return f'Created from completed booking #{booking.pk}'


def booking_completion_date(booking):
    if booking.completed_at:
        return timezone.localtime(booking.completed_at).date()
    return booking.date


def followup_exists_for_booking(booking):
    note = followup_note_for_booking(booking)
    return CustomerFollowUp.objects.filter(notes__contains=note).exists()


def create_followup_from_completed_booking(booking, interval_months=CustomerFollowUp.IntervalMonths.SIX):
    """Create an open follow-up dated from when the job was completed. Returns the follow-up or None."""
    if booking.status != BookingStatus.COMPLETED:
        return None
    if followup_exists_for_booking(booking):
        return None

    name = (booking.contact_full_name or '').strip()
    email = (booking.contact_email or '').strip()
    phone = (booking.contact_phone or '').strip()
    if not name or (not email and not phone):
        return None

    interval_months = int(interval_months)
    due_date = CustomerFollowUp.due_date_from_interval(
        interval_months,
        from_date=booking_completion_date(booking),
    )
    return CustomerFollowUp.objects.create(
        name=name,
        phone=phone,
        email=email,
        interval_months=interval_months,
        due_date=due_date,
        notes=followup_note_for_booking(booking),
    )
