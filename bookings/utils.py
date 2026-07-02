from datetime import date, timedelta

from django.utils import timezone

from bookings.models import Availability, BlockedDate, Booking, BookingStatus, TimeSlot, WeeklySchedule
from bookings.scheduling import get_feasible_slots
from bookings.routing import coords_for_address


def is_weekly_closed(day):
    schedule = WeeklySchedule.objects.filter(day_of_week=day.weekday()).first()
    return bool(schedule and not schedule.is_available)


def is_day_available(date):
    if BlockedDate.objects.filter(date=date).exists():
        return False
    return not is_weekly_closed(date)


def get_calendar_dates_in_month(year, month, service_ids=None, postcode='', city='', exclude_booking_pk=None):
    """Classify each future day in the month for the booking calendar."""
    from calendar import monthrange

    today = timezone.localdate()
    _, last_day = monthrange(year, month)
    start = max(today, date(year, month, 1))
    end = date(year, month, last_day)

    weekly_closed = {
        row.day_of_week
        for row in WeeklySchedule.objects.filter(is_available=False)
    }
    blocked = {
        row.date: row.closure_type
        for row in BlockedDate.objects.filter(date__gte=start, date__lte=end)
    }

    available = []
    closed = []
    full = []

    current = start
    while current <= end:
        iso = current.isoformat()
        if current.weekday() in weekly_closed:
            closed.append(iso)
        elif current in blocked:
            if blocked[current] == BlockedDate.ClosureType.FULL:
                full.append(iso)
            else:
                closed.append(iso)
        else:
            slots = get_available_slots_for_date(
                current,
                service_ids=service_ids,
                postcode=postcode,
                city=city,
                exclude_booking_pk=exclude_booking_pk,
            )
            if slots.exists():
                available.append(iso)
            else:
                full.append(iso)
        current += timedelta(days=1)

    return {'available': available, 'closed': closed, 'full': full}


def get_available_dates_in_month(year, month, service_ids=None, postcode='', city=''):
    return get_calendar_dates_in_month(
        year, month,
        service_ids=service_ids,
        postcode=postcode,
        city=city,
    )['available']


def find_next_available_date(service_ids=None, postcode='', city='', max_months=6, exclude_booking_pk=None):
    """Return ISO date string of the next bookable day, or None."""
    today = timezone.localdate()
    year, month = today.year, today.month
    for _ in range(max_months):
        calendar = get_calendar_dates_in_month(
            year, month,
            service_ids=service_ids,
            postcode=postcode,
            city=city,
            exclude_booking_pk=exclude_booking_pk,
        )
        if calendar['available']:
            return calendar['available'][0]
        month += 1
        if month > 12:
            month = 1
            year += 1
    return None


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
    promo_id = booking.promo_code_id
    booking.status = BookingStatus.CANCELLED
    booking.save(update_fields=['status', 'updated_at'])
    if promo_id:
        from bookings.promo import release_promo_use
        release_promo_use(promo_id)
    if notify:
        from bookings.notifications import send_booking_status_email
        send_booking_status_email(booking)
    return True

