"""Travel-aware booking schedule checks."""

from datetime import datetime, timedelta

from django.conf import settings
from django.utils import timezone

from bookings.models import Availability, BlockedDate, Booking, BookingStatus, TimeSlot, WeeklySchedule
from bookings.routing import coords_for_address, geocode_booking, travel_minutes
from services.models import Service


def get_service_duration_minutes(service_ids):
    if not service_ids:
        return getattr(settings, 'DEFAULT_JOB_DURATION_MINUTES', 60)

    services = Service.objects.filter(pk__in=service_ids)
    total = sum(s.duration_minutes for s in services)
    return total or getattr(settings, 'DEFAULT_JOB_DURATION_MINUTES', 60)


def get_booking_duration_minutes(booking):
    if booking.estimated_duration_minutes:
        return booking.estimated_duration_minutes
    service_ids = list(booking.get_services().values_list('pk', flat=True))
    return get_service_duration_minutes(service_ids)


class ScheduledJob:
    __slots__ = ('booking', 'start', 'end', 'duration', 'coords')

    def __init__(self, booking, start, duration, coords):
        self.booking = booking
        self.start = start
        self.duration = duration
        self.end = start + timedelta(minutes=duration)
        self.coords = coords


def get_day_jobs(date, exclude_booking_pk=None):
    bookings = Booking.objects.filter(
        date=date,
    ).exclude(
        status=BookingStatus.CANCELLED,
    ).select_related('time_slot').prefetch_related('services')

    if exclude_booking_pk:
        bookings = bookings.exclude(pk=exclude_booking_pk)

    jobs = []
    for booking in bookings.order_by('time_slot__time'):
        start = timezone.make_aware(datetime.combine(date, booking.time_slot.time))
        duration = get_booking_duration_minutes(booking)
        coords = geocode_booking(booking)
        jobs.append(ScheduledJob(booking, start, duration, coords))
    return jobs


def _slot_start(date, slot_time):
    return timezone.make_aware(datetime.combine(date, slot_time))


def _format_time(dt):
    return dt.strftime('%H:%M')


def _travel_gap(from_coords, to_coords):
    if not from_coords or not to_coords:
        return getattr(settings, 'DEFAULT_TRAVEL_MINUTES', 30), 'default (missing coords)'
    return travel_minutes(from_coords, to_coords), 'OSRM/estimate'


def _job_debug_info(job):
    return {
        'booking_id': job.booking.pk,
        'start': _format_time(job.start),
        'end': _format_time(job.end),
        'busy_until': _format_time(job.end),
        'duration_minutes': job.duration,
        'postcode': job.booking.postcode,
        'address': job.booking.full_address(),
        'coords': [float(job.coords[0]), float(job.coords[1])] if job.coords else None,
        'services': job.booking.service_summary,
    }


def _find_prev_next_jobs(jobs, start):
    prev_job = None
    next_job = None
    for job in jobs:
        if job.start < start:
            prev_job = job
        elif job.start > start and next_job is None:
            next_job = job
            break
    return prev_job, next_job


def explain_slot(date, slot_time, duration_minutes, candidate_coords, jobs):
    """Return feasibility plus human-readable reasons (for debug)."""
    details = {
        'slot_time': slot_time.strftime('%H:%M'),
        'job_duration_minutes': duration_minutes,
        'feasible': False,
        'checks': [],
    }

    if not candidate_coords:
        details['checks'].append({
            'status': 'fail',
            'rule': 'geocode',
            'message': 'No coordinates for candidate postcode',
        })
        return details

    start = _slot_start(date, slot_time)
    end = start + timedelta(minutes=duration_minutes)
    details['job_end'] = _format_time(end)

    if date == timezone.localdate() and start <= timezone.localtime():
        details['checks'].append({
            'status': 'fail',
            'rule': 'past',
            'message': 'Slot is in the past',
        })
        return details

    for job in jobs:
        if start < job.end and end > job.start:
            details['checks'].append({
                'status': 'fail',
                'rule': 'overlap',
                'message': (
                    f'On-site work would overlap booking #{job.booking.pk} '
                    f'({_format_time(job.start)}–{_format_time(job.end)}, {job.duration} min on site)'
                ),
                'job': _job_debug_info(job),
            })
            return details

    prev_job, next_job = _find_prev_next_jobs(jobs, start)

    if prev_job:
        gap, gap_source = _travel_gap(prev_job.coords, candidate_coords)
        earliest = prev_job.end + timedelta(minutes=gap)
        ok = start >= earliest
        details['checks'].append({
            'status': 'pass' if ok else 'fail',
            'rule': 'travel_from_previous',
            'message': (
                f'After previous job #{prev_job.booking.pk} (busy until {_format_time(prev_job.end)}), '
                f'drive {gap} min ({gap_source}) to your address. Earliest start: {_format_time(earliest)}.'
            ),
            'travel_minutes': gap,
            'travel_source': gap_source,
            'earliest_start': _format_time(earliest),
            'previous_job': _job_debug_info(prev_job),
        })
        if not ok:
            return details

    if next_job:
        gap, gap_source = _travel_gap(candidate_coords, next_job.coords)
        must_finish_by = next_job.start - timedelta(minutes=gap)
        ok = end <= must_finish_by
        details['checks'].append({
            'status': 'pass' if ok else 'fail',
            'rule': 'travel_to_next',
            'message': (
                f'Next job #{next_job.booking.pk} starts {_format_time(next_job.start)} '
                f'(busy until {_format_time(next_job.end)}) at {next_job.booking.postcode}. '
                f'Your job ends {_format_time(end)}, then {gap} min drive ({gap_source}). '
                f'Must finish on site by {_format_time(must_finish_by)}.'
            ),
            'travel_minutes': gap,
            'travel_source': gap_source,
            'must_finish_by': _format_time(must_finish_by),
            'next_job': _job_debug_info(next_job),
        })
        if not ok:
            return details

    if not prev_job and not next_job:
        details['checks'].append({
            'status': 'pass',
            'rule': 'first_job',
            'message': 'No other jobs this day — slot is clear',
        })
    elif not prev_job and next_job:
        details['checks'].append({
            'status': 'pass',
            'rule': 'first_job_before_next',
            'message': (
                f'First job of the day — only needs to finish with travel time before '
                f'{_format_time(next_job.start)} (next appointment).'
            ),
        })
    else:
        details['checks'].append({
            'status': 'pass',
            'rule': 'all_checks',
            'message': 'All travel and overlap checks passed',
        })

    details['feasible'] = True
    return details


def is_slot_feasible(date, slot_time, duration_minutes, candidate_coords, jobs):
    return explain_slot(date, slot_time, duration_minutes, candidate_coords, jobs)['feasible']


def get_schedule_debug(date, service_ids=None, postcode='', city='', exclude_booking_pk=None):
    """Full debug breakdown for a day's scheduling."""
    from bookings.routing import normalize_postcode

    duration = get_service_duration_minutes(service_ids or [])
    candidate_coords = coords_for_address(postcode, city)
    jobs = get_day_jobs(date, exclude_booking_pk=exclude_booking_pk)

    unavailable_ids = set(
        Availability.objects.filter(date=date, available=False).values_list('time_slot_id', flat=True)
    )

    slot_analysis = []
    for slot in TimeSlot.objects.filter(active=True).order_by('time'):
        if slot.pk in unavailable_ids:
            slot_analysis.append({
                'time': slot.time.strftime('%H:%M'),
                'slot_id': slot.pk,
                'available': False,
                'blocked_by': 'admin_availability',
                'explanation': 'Blocked in admin availability',
            })
            continue

        explanation = explain_slot(date, slot.time, duration, candidate_coords, jobs)
        slot_analysis.append({
            'time': slot.time.strftime('%H:%M'),
            'slot_id': slot.pk,
            'available': explanation['feasible'],
            'blocked_by': None if explanation['feasible'] else (
                explanation['checks'][-1]['rule'] if explanation['checks'] else 'unknown'
            ),
            'explanation': explanation,
        })

    return {
        'date': date.isoformat(),
        'postcode': normalize_postcode(postcode),
        'city': city,
        'candidate_coords': [float(candidate_coords[0]), float(candidate_coords[1])] if candidate_coords else None,
        'service_ids': service_ids or [],
        'job_duration_minutes': duration,
        'existing_jobs': [_job_debug_info(job) for job in jobs],
        'existing_job_count': len(jobs),
        'slots': slot_analysis,
        'available_count': sum(1 for s in slot_analysis if s['available']),
        'total_slots': len(slot_analysis),
    }


def _is_day_available(date):
    if BlockedDate.objects.filter(date=date).exists():
        return False
    schedule = WeeklySchedule.objects.filter(day_of_week=date.weekday()).first()
    return schedule.is_available if schedule else True


def get_feasible_slots(date, service_ids=None, postcode='', city='', exclude_booking_pk=None):
    if not _is_day_available(date):
        return TimeSlot.objects.none()

    duration = get_service_duration_minutes(service_ids or [])
    candidate_coords = coords_for_address(postcode, city)
    if not candidate_coords:
        return TimeSlot.objects.none()

    jobs = get_day_jobs(date, exclude_booking_pk=exclude_booking_pk)

    unavailable_ids = set(
        Availability.objects.filter(
            date=date,
            available=False,
        ).values_list('time_slot_id', flat=True)
    )

    feasible = []
    for slot in TimeSlot.objects.filter(active=True).order_by('time'):
        if slot.pk in unavailable_ids:
            continue
        if is_slot_feasible(date, slot.time, duration, candidate_coords, jobs):
            feasible.append(slot.pk)

    return TimeSlot.objects.filter(pk__in=feasible).order_by('time')


def validate_booking_schedule(date, slot_time, service_ids, postcode, city='', exclude_booking_pk=None):
    duration = get_service_duration_minutes(service_ids)
    coords = coords_for_address(postcode, city)
    if not coords:
        return False, 'We could not locate that postcode. Please check it and try again.'

    jobs = get_day_jobs(date, exclude_booking_pk=exclude_booking_pk)
    if is_slot_feasible(date, slot_time, duration, coords, jobs):
        return True, ''

    return False, (
        'This time is no longer available — there is not enough time to complete your '
        'clean and drive to the next appointment. Please choose another slot.'
    )


def get_day_schedule_panel_data(date):
    """Build day timeline + travel legs for the admin schedule view."""
    from bookings.routing import osrm_route_geometry

    jobs = get_day_jobs(date)
    panel_jobs = []
    legs = []

    for index, job in enumerate(jobs):
        info = _job_debug_info(job)
        info.update({
            'status': job.booking.status,
            'customer': job.booking.contact_full_name or 'Guest',
            'phone': job.booking.contact_phone or '',
            'services': job.booking.service_summary,
            'city': job.booking.city,
            'edit_path': f'/panel/bookings/{job.booking.pk}/edit/',
        })
        panel_jobs.append(info)

        if index == 0:
            continue

        prev_job = jobs[index - 1]
        gap, gap_source = _travel_gap(prev_job.coords, job.coords)
        geometry = []
        if prev_job.coords and job.coords:
            geometry = osrm_route_geometry(prev_job.coords, job.coords)

        legs.append({
            'from_booking_id': prev_job.booking.pk,
            'to_booking_id': job.booking.pk,
            'travel_minutes': gap,
            'travel_source': gap_source,
            'geometry': geometry,
        })

    return {
        'date': date.isoformat(),
        'jobs': panel_jobs,
        'legs': legs,
        'job_count': len(panel_jobs),
    }


def get_week_schedule_summary(week_start):
    """Return booking counts per date for a 7-day week starting week_start."""
    from datetime import timedelta

    from django.db.models import Count

    end = week_start + timedelta(days=6)
    counts = (
        Booking.objects.filter(date__gte=week_start, date__lte=end)
        .exclude(status=BookingStatus.CANCELLED)
        .values('date')
        .annotate(count=Count('id'))
        .order_by('date')
    )
    count_map = {row['date']: row['count'] for row in counts}
    days = []
    for offset in range(7):
        day = week_start + timedelta(days=offset)
        days.append({
            'date': day.isoformat(),
            'weekday': day.strftime('%a'),
            'label': day.strftime('%d %b'),
            'count': count_map.get(day, 0),
            'is_today': day == timezone.localdate(),
        })
    return days
