from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from bookings.forms import BookingForm
from bookings.models import Booking
from bookings.notifications import send_booking_created_email
from bookings.utils import cancel_booking, get_available_dates_in_month, get_available_slots_for_date
from services.models import Service, ServiceType


@login_required
def create_booking_view(request):
    if request.method == 'POST':
        form = BookingForm(request.POST)
        if form.is_valid():
            booking = form.save(commit=False)
            booking.user = request.user
            service_ids = [s.pk for s in form.cleaned_data['services']]
            booking.save()
            booking.services.set(form.cleaned_data['services'])
            booking.geocode_and_set_duration(service_ids)
            if send_booking_created_email(booking):
                messages.success(
                    request,
                    'Your booking has been submitted successfully! You will receive a confirmation email shortly.',
                )
            else:
                messages.success(
                    request,
                    'Your booking has been submitted successfully! '
                    'We could not send a confirmation email, but your booking is saved.',
                )
            return redirect('accounts:my_bookings')
    else:
        initial = {}
        service_id = request.GET.get('service')
        if service_id:
            initial['services'] = [service_id]
        form = BookingForm(initial=initial)

    selected_service = None
    service_id = request.GET.get('service')
    if service_id:
        selected_service = Service.objects.filter(pk=service_id, active=True).first()

    services = Service.objects.filter(active=True)
    oven_services = services.filter(service_type=ServiceType.OVEN)
    addon_services = services.filter(service_type=ServiceType.ADDON)
    return render(request, 'bookings/create.html', {
        'form': form,
        'selected_service': selected_service,
        'oven_services': oven_services,
        'addon_services': addon_services,
        'schedule_debug': settings.SCHEDULE_DEBUG,
    })


@login_required
def booking_detail_view(request, pk):
    booking = get_object_or_404(Booking, pk=pk, user=request.user)
    return render(request, 'bookings/detail.html', {'booking': booking})


@login_required
@require_POST
def cancel_booking_view(request, pk):
    booking = get_object_or_404(Booking, pk=pk, user=request.user)
    if not booking.is_cancellable:
        messages.error(request, 'This booking cannot be cancelled.')
        return redirect('bookings:detail', pk=booking.pk)
    cancel_booking(booking)
    messages.success(request, 'Your booking has been cancelled.')
    return redirect('accounts:my_bookings')


def _parse_service_ids(request):
    ids = request.GET.getlist('services') or request.GET.get('services', '').split(',')
    return [int(pk) for pk in ids if str(pk).strip().isdigit()]


@login_required
@require_GET
def available_dates_api(request):
    try:
        year = int(request.GET.get('year', ''))
        month = int(request.GET.get('month', ''))
        if month < 1 or month > 12:
            raise ValueError
    except (TypeError, ValueError):
        return JsonResponse({'available': []})

    service_ids = _parse_service_ids(request)
    postcode = request.GET.get('postcode', '').strip()
    city = request.GET.get('city', '').strip()
    available = get_available_dates_in_month(
        year, month,
        service_ids=service_ids or None,
        postcode=postcode,
        city=city,
    )
    return JsonResponse({'available': available, 'year': year, 'month': month})


@login_required
@require_GET
def available_slots_api(request):
    date_str = request.GET.get('date')
    if not date_str:
        return JsonResponse({'slots': []})
    try:
        from datetime import datetime
        date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return JsonResponse({'slots': []})

    service_ids = _parse_service_ids(request)
    postcode = request.GET.get('postcode', '').strip()
    city = request.GET.get('city', '').strip()

    if not postcode:
        return JsonResponse({'slots': [], 'error': 'postcode_required'})

    duration = None
    if service_ids:
        from bookings.scheduling import get_service_duration_minutes
        duration = get_service_duration_minutes(service_ids)

    slots = get_available_slots_for_date(
        date,
        service_ids=service_ids or None,
        postcode=postcode,
        city=city,
    )
    payload = {
        'slots': [{'id': s.pk, 'time': s.time.strftime('%H:%M')} for s in slots],
        'estimated_duration_minutes': duration,
    }
    if settings.SCHEDULE_DEBUG or request.GET.get('debug') == '1':
        from bookings.scheduling import get_schedule_debug
        try:
            payload['debug'] = get_schedule_debug(
                date,
                service_ids=service_ids,
                postcode=postcode,
                city=city,
            )
        except Exception as exc:
            payload['debug_error'] = str(exc)
    return JsonResponse(payload)
