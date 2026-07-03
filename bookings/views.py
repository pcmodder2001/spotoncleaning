from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST
import json
import mimetypes

from bookings.completion_report import (
    booking_from_completion_report_token,
    get_completion_report_context,
)
from bookings.forms import BookingForm, GuestBookingForm, RescheduleBookingForm
from bookings.ics import build_booking_ics
from bookings.models import Booking, BookingPhoto, BookingStatus
from bookings.photo_access import can_view_booking_photo
from bookings.notifications import send_booking_created_email, send_booking_rescheduled_email
from bookings.service_area import is_postcode_in_service_area, service_area_error_message
from bookings.utils import (
    cancel_booking,
    find_next_available_date,
    get_calendar_dates_in_month,
    get_available_slots_for_date,
)
from audit.actions import BOOKING_CANCELLED, BOOKING_CREATED, BOOKING_RESCHEDULED
from audit.services import log_action
from services.catalog import split_addon_services
from services.models import Service, ServiceType
from website.tracking import queue_meta_pixel_event, apply_marketing_attribution


def _booking_prefill_address(user):
    if not user.is_authenticated:
        return None
    if user.is_business_account:
        from accounts.business import get_default_property
        prop = get_default_property(user)
        if prop:
            return prop.as_booking_dict()
    from accounts.addresses import get_default_saved_address, import_addresses_from_bookings

    import_addresses_from_bookings(user)
    saved = get_default_saved_address(user)
    if saved:
        return {
            'id': saved.pk,
            'address_line_1': saved.address_line_1,
            'address_line_2': saved.address_line_2 or '',
            'city': saved.city,
            'postcode': saved.postcode,
        }
    last = (
        Booking.objects.filter(user=user)
        .exclude(status=BookingStatus.CANCELLED)
        .order_by('-date', '-created_at')
        .first()
    )
    if not last:
        return None
    return {
        'address_line_1': last.address_line_1,
        'address_line_2': last.address_line_2 or '',
        'city': last.city,
        'postcode': last.postcode,
    }


def _saved_addresses_json(user):
    if not user.is_authenticated:
        return '[]'
    if user.is_business_account:
        from accounts.business import get_properties_for_user
        properties = [
            prop.as_booking_dict()
            for prop in get_properties_for_user(user)
        ]
        return json.dumps(properties)
    from accounts.addresses import get_saved_addresses_for_user, import_addresses_from_bookings

    import_addresses_from_bookings(user)
    addresses = [
        address.as_booking_dict()
        for address in get_saved_addresses_for_user(user)
    ]
    return json.dumps(addresses)


def _booking_create_context(request, form):
    service_id = request.GET.get('service') or request.POST.get('services')
    selected_service = None
    if service_id:
        if isinstance(service_id, list):
            service_id = service_id[0] if service_id else None
        if service_id:
            selected_service = Service.objects.filter(pk=service_id, active=True).first()

    services = Service.objects.filter(active=True)
    oven_services = services.filter(service_type=ServiceType.OVEN)
    addon_services = services.filter(service_type=ServiceType.ADDON)
    standard_addon_services, additional_addon_services = split_addon_services(addon_services)
    prefill_address = _booking_prefill_address(request.user)
    return {
        'form': form,
        'selected_service': selected_service,
        'oven_services': oven_services,
        'standard_addon_services': standard_addon_services,
        'additional_addon_services': additional_addon_services,
        'schedule_debug': settings.SCHEDULE_DEBUG,
        'is_guest_booking': not request.user.is_authenticated,
        'is_business_account': request.user.is_authenticated and request.user.is_business_account,
        'prefill_address': prefill_address,
        'prefill_address_json': json.dumps(prefill_address) if prefill_address else 'null',
        'saved_addresses_json': _saved_addresses_json(request.user),
    }


def _attach_booking_property(booking, request):
    if not request.user.is_authenticated or not request.user.is_business_account:
        return
    property_id = request.POST.get('property_id', '').strip()
    if not property_id or not property_id.isdigit():
        return
    from accounts.models import Property
    prop = Property.objects.filter(pk=int(property_id), user=request.user).first()
    if not prop:
        return
    booking.rental_property = prop
    if prop.access_instructions:
        booking.access_instructions = prop.access_instructions
    booking.save(update_fields=['rental_property', 'access_instructions', 'updated_at'])


def create_booking_view(request):
    form_class = BookingForm if request.user.is_authenticated else GuestBookingForm
    if request.method == 'POST':
        form = form_class(request.POST)
        if form.is_valid():
            from bookings.promo import PromoError, record_promo_use

            try:
                with transaction.atomic():
                    if request.user.is_authenticated:
                        booking = form.save(commit=False)
                        booking.user = request.user
                        service_ids = [s.pk for s in form.cleaned_data['services']]
                        booking.save()
                        booking.services.set(form.cleaned_data['services'])
                        _attach_booking_property(booking, request)
                        booking.geocode_and_set_duration(service_ids)
                        if request.POST.get('save_address') == '1':
                            from accounts.addresses import save_address_for_user
                            save_address_for_user(
                                request.user,
                                address_line_1=form.cleaned_data['address_line_1'],
                                address_line_2=form.cleaned_data.get('address_line_2', ''),
                                city=form.cleaned_data['city'],
                                postcode=form.cleaned_data['postcode'],
                                is_default=request.POST.get('save_address_default') == '1',
                            )
                    else:
                        booking = form.save()

                    promo = form.cleaned_data.get('_promo')
                    if promo:
                        record_promo_use(promo.pk)
            except PromoError as exc:
                messages.error(request, str(exc))
                return render(
                    request,
                    'bookings/create.html',
                    _booking_create_context(request, form),
                )
            apply_marketing_attribution(booking, request)
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
            queue_meta_pixel_event(
                request,
                'Schedule',
                value=float(booking.total_price),
                currency='GBP',
                content_name='Appliance cleaning booking',
            )
            request.session['booking_confirmation_id'] = booking.pk
            return redirect('bookings:thank_you')
    else:
        initial = {}
        service_id = request.GET.get('service')
        if service_id:
            initial['services'] = [service_id]
        postcode_query = request.GET.get('postcode', '').strip()
        if postcode_query:
            from bookings.routing import normalize_postcode
            initial['postcode'] = normalize_postcode(postcode_query)
        prefill = _booking_prefill_address(request.user)
        if prefill and not postcode_query:
            initial.setdefault('postcode', prefill['postcode'])
        if prefill:
            initial.setdefault('address_line_1', prefill['address_line_1'])
            initial.setdefault('address_line_2', prefill['address_line_2'])
            initial.setdefault('city', prefill['city'])
        form = form_class(initial=initial)
        queue_meta_pixel_event(
            request,
            'ViewContent',
            content_name='Book a clean',
            content_category='Booking',
        )

    return render(
        request,
        'bookings/create.html',
        _booking_create_context(request, form),
    )


def thank_you_view(request):
    booking_id = request.session.get('booking_confirmation_id')
    booking = None
    if booking_id:
        booking = (
            Booking.objects.filter(pk=booking_id)
            .select_related('time_slot')
            .prefetch_related('services')
            .first()
        )
    return render(request, 'bookings/thank_you.html', {'booking': booking})


@require_GET
def booking_calendar_ics_view(request):
    booking_id = request.session.get('booking_confirmation_id')
    if not booking_id:
        raise Http404
    booking = get_object_or_404(
        Booking.objects.select_related('time_slot'),
        pk=booking_id,
    )
    ics_body = build_booking_ics(booking)
    response = HttpResponse(ics_body, content_type='text/calendar; charset=utf-8')
    response['Content-Disposition'] = (
        f'attachment; filename="spot-on-booking-{booking.pk}.ics"'
    )
    return response


@login_required
def booking_detail_view(request, pk):
    booking = get_object_or_404(
        Booking.objects.select_related('time_slot', 'promo_code', 'rental_property').prefetch_related('services'),
        pk=pk,
        user=request.user,
    )
    return render(request, 'bookings/detail.html', {
        'booking': booking,
        'show_completion_report': booking.status == BookingStatus.COMPLETED,
    })


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


@login_required
def reschedule_booking_view(request, pk):
    booking = get_object_or_404(
        Booking.objects.select_related('time_slot').prefetch_related('services'),
        pk=pk,
        user=request.user,
    )
    if not booking.is_reschedulable:
        messages.error(request, 'This booking cannot be rescheduled.')
        return redirect('bookings:detail', pk=booking.pk)

    if request.method == 'POST':
        form = RescheduleBookingForm(request.POST, booking=booking)
        if form.is_valid():
            old_date = booking.date
            old_time = booking.time_slot.time
            was_confirmed = booking.status == BookingStatus.CONFIRMED
            booking.date = form.cleaned_data['date']
            booking.time_slot = form.cleaned_data['time_slot']
            booking.status = BookingStatus.PENDING
            booking.reminder_sent_at = None
            booking.save(update_fields=[
                'date', 'time_slot', 'status', 'reminder_sent_at', 'updated_at',
            ])
            send_booking_rescheduled_email(booking, needs_confirmation=was_confirmed)
            log_action(
                BOOKING_RESCHEDULED,
                (
                    f'Customer rescheduled booking #{booking.pk} from '
                    f'{old_date} {old_time.strftime("%H:%M")} to '
                    f'{booking.date} {booking.time_slot.time.strftime("%H:%M")}.'
                ),
                request=request,
                user=request.user,
                target_type='booking',
                target_id=booking.pk,
                target_label=f'Booking #{booking.pk}',
                metadata={
                    'old_date': old_date.isoformat(),
                    'old_time': old_time.strftime('%H:%M'),
                    'new_date': booking.date.isoformat(),
                    'new_time': booking.time_slot.time.strftime('%H:%M'),
                },
            )
            if was_confirmed:
                messages.success(
                    request,
                    'Your appointment has been rescheduled. We will confirm the new date and time shortly.',
                )
            else:
                messages.success(request, 'Your appointment has been rescheduled.')
            return redirect('bookings:detail', pk=booking.pk)
    else:
        form = RescheduleBookingForm(booking=booking)

    service_ids = list(booking.get_services().values_list('pk', flat=True))
    initial_date = ''
    initial_time_slot = ''
    if form.is_bound:
        initial_date = form.data.get('date', '')
        initial_time_slot = form.data.get('time_slot', '')
    elif booking:
        initial_date = booking.date.isoformat()
        initial_time_slot = str(booking.time_slot_id)

    return render(request, 'bookings/reschedule.html', {
        'booking': booking,
        'form': form,
        'service_ids_json': json.dumps(service_ids),
        'initial_date': initial_date,
        'initial_time_slot': initial_time_slot,
    })


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
def available_dates_api(request):
    try:
        year = int(request.GET.get('year', ''))
        month = int(request.GET.get('month', ''))
        if month < 1 or month > 12:
            raise ValueError
    except (TypeError, ValueError):
        return JsonResponse({'available': [], 'closed': [], 'full': []})

    service_ids = _parse_service_ids(request)
    postcode = request.GET.get('postcode', '').strip()
    city = request.GET.get('city', '').strip()
    if postcode:
        area_error = _service_area_api_error(postcode)
        if area_error:
            return area_error
    exclude_booking_pk = request.GET.get('exclude_booking')
    if exclude_booking_pk and str(exclude_booking_pk).isdigit():
        exclude_booking_pk = int(exclude_booking_pk)
    else:
        exclude_booking_pk = None
    calendar = get_calendar_dates_in_month(
        year, month,
        service_ids=service_ids or None,
        postcode=postcode,
        city=city,
        exclude_booking_pk=exclude_booking_pk,
    )
    payload = {
        'available': calendar['available'],
        'closed': calendar['closed'],
        'full': calendar['full'],
        'year': year,
        'month': month,
    }
    if postcode:
        payload['next_available'] = find_next_available_date(
            service_ids=service_ids or None,
            postcode=postcode,
            city=city,
            exclude_booking_pk=exclude_booking_pk,
        )
    return JsonResponse(payload)


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
    exclude_booking_pk = request.GET.get('exclude_booking')
    if exclude_booking_pk and str(exclude_booking_pk).isdigit():
        exclude_booking_pk = int(exclude_booking_pk)
    else:
        exclude_booking_pk = None

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
        exclude_booking_pk=exclude_booking_pk,
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


@require_GET
def validate_promo_api(request):
    code = request.GET.get('code', '').strip()
    if not code:
        return JsonResponse({'valid': False, 'error': 'Enter a promo code.'})

    service_ids = _parse_service_ids(request)
    if not service_ids:
        return JsonResponse({'valid': False, 'error': 'Select at least one service first.'})

    from decimal import Decimal

    from bookings.promo import PromoError, get_valid_promo
    from services.models import Service

    try:
        promo = get_valid_promo(code)
        subtotal = sum(
            s.price for s in Service.objects.filter(pk__in=service_ids)
        )
        discount = promo.calculate_discount(subtotal)
        if discount <= 0:
            return JsonResponse({
                'valid': False,
                'error': (
                    f'This code requires a minimum order of '
                    f'£{promo.min_order_amount:.2f}.'
                ),
            })
        total = subtotal - discount
        return JsonResponse({
            'valid': True,
            'code': promo.code,
            'discount': str(discount.quantize(Decimal('0.01'))),
            'subtotal': str(subtotal.quantize(Decimal('0.01'))),
            'total': str(total.quantize(Decimal('0.01'))),
        })
    except PromoError as exc:
        return JsonResponse({'valid': False, 'error': str(exc)})
