from datetime import date, timedelta

from django.utils import timezone

from bookings.models import Availability, BlockedDate, Booking, BookingStatus, TimeSlot, WeeklySchedule
from bookings.scheduling import get_feasible_slots
from bookings.routing import coords_for_address


def is_day_available(date):
    if BlockedDate.objects.filter(date=date).exists():
        return False
    schedule = WeeklySchedule.objects.filter(day_of_week=date.weekday()).first()
    return schedule.is_available if schedule else True


def get_available_slots_for_date(date, service_ids=None, postcode='', city='', exclude_booking_pk=None):
    if service_ids or postcode:
        return get_feasible_slots(
            date,
            service_ids=service_ids,
            postcode=postcode,
            city=city,
            exclude_booking_pk=exclude_booking_pk,
        )

    if not is_day_available(date):
        return TimeSlot.objects.none()

    active_slots = TimeSlot.objects.filter(active=True)
    booked_slot_ids = Booking.objects.filter(
        date=date,
    ).exclude(
        status=BookingStatus.CANCELLED,
    ).values_list('time_slot_id', flat=True)

    unavailable_ids = Availability.objects.filter(
        date=date,
        available=False,
    ).values_list('time_slot_id', flat=True)

    excluded = set(booked_slot_ids) | set(unavailable_ids)
    slots = active_slots.exclude(pk__in=excluded)

    if date == timezone.localdate():
        now = timezone.localtime().time()
        slots = slots.filter(time__gt=now)

    return slots


def get_time_slots_for_booking_edit(date, booking_pk=None, service_ids=None, postcode='', city=''):
    """Available slots for admin edit, always including the booking's current slot."""
    if booking_pk:
        booking = Booking.objects.filter(pk=booking_pk).first()
        if booking:
            service_ids = service_ids or list(booking.get_services().values_list('pk', flat=True))
            postcode = postcode or booking.postcode
            city = city or booking.city

    if postcode and coords_for_address(postcode, city):
        slots = get_feasible_slots(
            date,
            service_ids=service_ids,
            postcode=postcode,
            city=city,
            exclude_booking_pk=booking_pk,
        )
    else:
        slots = get_available_slots_for_date(date)

    if booking_pk:
        booking = Booking.objects.filter(pk=booking_pk).select_related('time_slot').first()
        if booking and booking.date == date:
            current = TimeSlot.objects.filter(pk=booking.time_slot_id)
            slots = (slots | current).distinct().order_by('time')
    return slots


def cancel_booking(booking, *, notify=True):
    """Cancel a booking and optionally notify the customer."""
    if booking.status == BookingStatus.CANCELLED:
        return False
    booking.status = BookingStatus.CANCELLED
    booking.save(update_fields=['status', 'updated_at'])
    if notify:
        from bookings.notifications import send_booking_status_email
        send_booking_status_email(booking)
    return True


def get_available_dates_in_month(year, month, service_ids=None, postcode='', city=''):
    from calendar import monthrange

    today = timezone.localdate()
    _, last_day = monthrange(year, month)
    start = max(today, date(year, month, 1))
    end = date(year, month, last_day)

    dates = []
    current = start
    while current <= end:
        if is_day_available(current):
            slots = get_available_slots_for_date(
                current,
                service_ids=service_ids,
                postcode=postcode,
                city=city,
            )
            if slots.exists():
                dates.append(current.isoformat())
        current += timedelta(days=1)
    return dates
