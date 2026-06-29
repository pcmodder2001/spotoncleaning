from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST
import mimetypes

from bookings.address_lookup import get_address_lookup_api_key
from bookings.completion_report import (
    booking_from_completion_report_token,
    get_completion_report_context,
)
from bookings.forms import BookingForm, GuestBookingForm
from bookings.models import Booking, BookingPhoto, BookingStatus
from bookings.photo_access import can_view_booking_photo
from bookings.notifications import send_booking_created_email
from bookings.service_area import is_postcode_in_service_area, service_area_error_message
from bookings.utils import cancel_booking, get_available_dates_in_month, get_available_slots_for_date
from audit.actions import BOOKING_CANCELLED, BOOKING_CREATED
from audit.services import log_action
from services.catalog import split_addon_services
from services.models import Service, ServiceType


def create_booking_view(request):
    form_class = BookingForm if request.user.is_authenticated else GuestBookingForm
    if request.method == 'POST':
        form = form_class(request.POST)
        if form.is_valid():
            if request.user.is_authenticated:
                booking = form.save(commit=False)
                booking.user = request.user
                service_ids = [s.pk for s in form.cleaned_data['services']]
                booking.save()
                booking.services.set(form.cleaned_data['services'])
                booking.geocode_and_set_duration(service_ids)
            else:
                booking = form.save()
            log_action(
                BOOKING_CREATED,
                f'New booking #{booking.pk} for {booking.contact_full_name} on {booking.date}.',
                request=request,
                user=request.user if request.user.is_authenticated else None,
                actor_email=booking.contact_email,
                actor_name=booking.contact_full_name,
                target_type='booking',
                target_id=booking.pk,
                target_label=f'Booking #{booking.pk}',
                metadata={
                    'guest': not request.user.is_authenticated,
                    'services': booking.service_summary,
                },
            )
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
            if request.user.is_authenticated:
                return redirect('accounts:my_bookings')
            return redirect('bookings:thank_you')
    else:
        initial = {}
        service_id = request.GET.get('service')
        if service_id:
            initial['services'] = [service_id]
        form = form_class(initial=initial)

    selected_service = None
    service_id = request.GET.get('service')
    if service_id:
        selected_service = Service.objects.filter(pk=service_id, active=True).first()

    services = Service.objects.filter(active=True)
    oven_services = services.filter(service_type=ServiceType.OVEN)
    addon_services = services.filter(service_type=ServiceType.ADDON)
    standard_addon_services, additional_addon_services = split_addon_services(addon_services)
    return render(request, 'bookings/create.html', {
        'form': form,
        'selected_service': selected_service,
        'oven_services': oven_services,
        'standard_addon_services': standard_addon_services,
        'additional_addon_services': additional_addon_services,
        'schedule_debug': settings.SCHEDULE_DEBUG,
        'is_guest_booking': not request.user.is_authenticated,
        'address_lookup_enabled': (
            settings.ADDRESS_LOOKUP_ENABLED and bool(get_address_lookup_api_key())
        ),
    })


def thank_you_view(request):
    return render(request, 'bookings/thank_you.html')


@login_required
def booking_detail_view(request, pk):
    booking = get_object_or_404(Booking, pk=pk, user=request.user)
    return render(request, 'bookings/detail.html', {'booking': booking})


def completion_report_view(request, pk):
    booking = get_object_or_404(
        Booking.objects.select_related('time_slot', 'promo_code', 'user').prefetch_related(
            'services', 'photos'
        ),
        pk=pk,
        status=BookingStatus.COMPLETED,
    )

    token = request.GET.get('token', '').strip()
    authorized = False
    if request.user.is_authenticated and booking.user_id == request.user.id:
        authorized = True
    elif token and booking_from_completion_report_token(token) == booking:
        authorized = True

    if not authorized:
        raise Http404('Completion report not found.')

    context = get_completion_report_context(booking, request=request, access_token=token)
    return render(request, 'bookings/completion_report.html', context)


@require_GET
def booking_photo_view(request, pk, photo_pk):
    booking = get_object_or_404(Booking, pk=pk)
    photo = get_object_or_404(BookingPhoto, pk=photo_pk, booking=booking)
    token = request.GET.get('token', '').strip()

    if not can_view_booking_photo(request, booking, access_token=token):
        raise Http404('Photo not found.')
    if not photo.image:
        raise Http404('Photo not found.')

    content_type, _ = mimetypes.guess_type(photo.image.name)
    response = FileResponse(
        photo.image.open('rb'),
        content_type=content_type or 'image/jpeg',
    )
    response['Cache-Control'] = 'private, max-age=3600'
    return response


@login_required
@require_POST
def cancel_booking_view(request, pk):
    booking = get_object_or_404(Booking, pk=pk, user=request.user)
    if not booking.is_cancellable:
        messages.error(request, 'This booking cannot be cancelled.')
        return redirect('bookings:detail', pk=booking.pk)
    cancel_booking(booking)
    log_action(
        BOOKING_CANCELLED,
        f'Customer cancelled booking #{booking.pk}.',
        request=request,
        user=request.user,
        target_type='booking',
        target_id=booking.pk,
        target_label=f'Booking #{booking.pk}',
    )
    messages.success(request, 'Your booking has been cancelled.')
    return redirect('accounts:my_bookings')


def _parse_service_ids(request):
    ids = request.GET.getlist('services') or request.GET.get('services', '').split(',')
    return [int(pk) for pk in ids if str(pk).strip().isdigit()]


def _service_area_api_error(postcode):
    allowed, message = is_postcode_in_service_area(postcode)
    if allowed:
        return None
    return JsonResponse({
        'error': 'outside_service_area',
        'message': message or service_area_error_message(),
    }, status=400)


@require_GET
def address_lookup_api(request):
    from bookings.address_lookup import lookup_addresses

    if not settings.ADDRESS_LOOKUP_ENABLED:
        return JsonResponse({'addresses': [], 'error': 'disabled', 'manual_entry': True})

    postcode = request.GET.get('postcode', '').strip()
    if not postcode:
        return JsonResponse({'addresses': [], 'error': 'postcode_required'})
    area_error = _service_area_api_error(postcode)
    if area_error:
        return area_error
    return JsonResponse(lookup_addresses(postcode))


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
    if postcode:
        area_error = _service_area_api_error(postcode)
        if area_error:
            return area_error
    available = get_available_dates_in_month(
        year, month,
        service_ids=service_ids or None,
        postcode=postcode,
        city=city,
    )
    return JsonResponse({'available': available, 'year': year, 'month': month})


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

    area_error = _service_area_api_error(postcode)
    if area_error:
        return area_error

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
