from decimal import Decimal, InvalidOperation

from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from bookings.models import Booking, BookingPhoto, BookingStatus
from bookings.notifications import send_booking_status_email, send_booking_updated_email
from bookings.photo_access import booking_photo_url
from audit.actions import (
    BOOKING_JOB_COMPLETED,
    BOOKING_JOB_STARTED,
    BOOKING_SERVICES_UPDATED,
    BOOKING_UPDATED,
)
from audit.services import log_action
from panel.decorators import admin_required, panel_required
from panel.business_insights import booking_business_payload
from services.models import Service, ServiceType


def _booking_queryset_with_business():
    return Booking.objects.select_related(
        'time_slot',
        'promo_code',
        'user',
        'user__business_profile',
        'rental_property',
    ).prefetch_related('services', 'photos')


def _photo_url(request, photo):
    if not photo:
        return None
    return booking_photo_url(request, photo.booking, photo)


def _booking_pricing(booking):
    subtotal = booking.total_price
    discount = booking.discount_amount or Decimal('0.00')
    return {
        'subtotal': f'{subtotal:.2f}',
        'discount': f'{discount:.2f}',
        'total': f'{booking.discounted_total:.2f}',
        'has_discount': discount > 0,
        'has_promo': booking.has_promo,
        'promo_code': booking.promo_code.code if booking.promo_code_id else None,
        'promo_description': booking.promo_code.description if booking.promo_code_id else '',
    }


def _service_payload(request, booking, service):
    before = booking.photos.filter(
        service=service, photo_type=BookingPhoto.PhotoType.BEFORE
    ).first()
    after = booking.photos.filter(
        service=service, photo_type=BookingPhoto.PhotoType.AFTER
    ).first()
    return {
        'id': service.pk,
        'name': service.name,
        'price': f'{booking.service_price_for(service):.2f}',
        'service_type': service.service_type,
        'before_photo_url': _photo_url(request, before),
        'after_photo_url': _photo_url(request, after),
    }


def booking_detail_payload(request, booking):
    booking = _booking_queryset_with_business().get(pk=booking.pk)

    return {
        'id': booking.pk,
        'status': booking.status,
        'status_label': booking.get_status_display(),
        'date': booking.date.isoformat(),
        'time': booking.time_slot.time.strftime('%H:%M'),
        'customer': {
            'name': booking.contact_full_name or 'Guest',
            'email': booking.contact_email,
            'phone': booking.contact_phone or '',
        },
        'business_account': booking_business_payload(booking),
        'address': {
            'line1': booking.address_line_1,
            'line2': booking.address_line_2,
            'city': booking.city,
            'postcode': booking.postcode,
            'full': booking.full_address(),
        },
        'notes': booking.notes,
        'access_instructions': booking.access_instructions,
        'staff_notes': booking.staff_notes,
        'services': [_service_payload(request, booking, s) for s in booking.get_services()],
        'pricing': _booking_pricing(booking),
        'started_at': booking.started_at.isoformat() if booking.started_at else None,
        'completed_at': booking.completed_at.isoformat() if booking.completed_at else None,
        'signed_by_name': booking.signed_by_name,
        'has_signature': bool(booking.completion_signature),
        'completion_signature': booking.completion_signature if booking.completion_signature else None,
        'can_start': booking.status == BookingStatus.CONFIRMED,
        'can_complete': booking.status == BookingStatus.IN_PROGRESS,
        'can_manage_services': (
            request.user.can_manage_site
            and booking.status not in (BookingStatus.CANCELLED, BookingStatus.COMPLETED)
        ),
        'can_edit_discount': (
            request.user.can_manage_site
            and booking.status not in (BookingStatus.CANCELLED, BookingStatus.COMPLETED)
        ),
        'can_admin_edit': request.user.can_manage_site,
        'edit_url': f'/panel/bookings/{booking.pk}/edit/',
    }


@panel_required
@require_GET
def booking_detail_api(request, pk):
    booking = get_object_or_404(Booking, pk=pk)
    return JsonResponse(booking_detail_payload(request, booking))


@admin_required
@require_POST
def booking_update_services_api(request, pk):
    booking = get_object_or_404(Booking, pk=pk)
    if booking.status in (BookingStatus.CANCELLED, BookingStatus.COMPLETED):
        return JsonResponse({'error': 'Cannot change services on this booking.'}, status=400)

    try:
        service_ids = [int(value) for value in request.POST.getlist('service_ids') if value.isdigit()]
    except ValueError:
        return JsonResponse({'error': 'Invalid service selection.'}, status=400)

    if not service_ids:
        return JsonResponse({'error': 'Select at least one service.'}, status=400)

    services = list(Service.objects.filter(pk__in=service_ids, active=True))
    if len(services) != len(set(service_ids)):
        return JsonResponse({'error': 'One or more services are invalid.'}, status=400)

    hob_count = sum(1 for s in services if s.exclusive_group == 'hob')
    if hob_count > 1:
        return JsonResponse({'error': 'Only one hob size allowed per booking.'}, status=400)

    booking.services.set(services)
    booking.sync_pricing_snapshot(services, save=False)
    booking.geocode_and_set_duration(service_ids)
    booking.recalculate_pricing(save=True)

    log_action(
        BOOKING_SERVICES_UPDATED,
        f'Updated services on booking #{booking.pk} ({booking.service_summary}).',
        request=request,
        target_type='booking',
        target_id=booking.pk,
        target_label=f'Booking #{booking.pk}',
        metadata={'service_ids': service_ids},
    )

    return JsonResponse({
        'success': True,
        'booking': booking_detail_payload(request, booking),
    })


@admin_required
@require_POST
def booking_update_discount_api(request, pk):
    booking = get_object_or_404(Booking, pk=pk)
    if booking.status in (BookingStatus.CANCELLED, BookingStatus.COMPLETED):
        return JsonResponse({'error': 'Cannot change discount on this booking.'}, status=400)

    raw = request.POST.get('discount_amount', '').strip()
    try:
        discount = Decimal(raw or '0')
    except InvalidOperation:
        return JsonResponse({'error': 'Enter a valid discount amount.'}, status=400)

    if discount < 0:
        return JsonResponse({'error': 'Discount cannot be negative.'}, status=400)

    subtotal = booking.total_price
    if discount > subtotal:
        return JsonResponse(
            {'error': f'Discount cannot exceed the subtotal (£{subtotal:.2f}).'},
            status=400,
        )

    discount = discount.quantize(Decimal('0.01'))
    previous = booking.discount_amount or Decimal('0.00')
    previous_promo = booking.promo_code.code if booking.promo_code_id else None

    booking.discount_amount = discount
    if discount > 0 or booking.promo_code_id:
        booking.promo_code = None
    booking.save(update_fields=['discount_amount', 'promo_code', 'updated_at'])

    email_sent = None
    if discount != previous:
        email_sent = send_booking_updated_email(booking)

    log_action(
        BOOKING_UPDATED,
        f'Updated discount on booking #{booking.pk} to £{discount:.2f}.',
        request=request,
        target_type='booking',
        target_id=booking.pk,
        target_label=f'Booking #{booking.pk}',
        metadata={
            'previous_discount': str(previous),
            'previous_promo': previous_promo,
            'discount': str(discount),
        },
    )

    return JsonResponse({
        'success': True,
        'email_sent': email_sent,
        'booking': booking_detail_payload(request, booking),
    })


@panel_required
@require_POST
def booking_start_job_api(request, pk):
    booking = get_object_or_404(Booking, pk=pk)
    if booking.status != BookingStatus.CONFIRMED:
        return JsonResponse(
            {'error': 'Confirm this booking before starting the job.'},
            status=400,
        )

    services = list(booking.get_services())
    if not services:
        return JsonResponse({'error': 'No services on this booking.'}, status=400)

    for service in services:
        field_name = f'before_{service.pk}'
        upload = request.FILES.get(field_name)
        if not upload:
            return JsonResponse(
                {'error': f'Before photo required for {service.name}.'},
                status=400,
            )
        BookingPhoto.objects.filter(
            booking=booking,
            service=service,
            photo_type=BookingPhoto.PhotoType.BEFORE,
        ).delete()
        BookingPhoto.objects.create(
            booking=booking,
            service=service,
            image=upload,
            photo_type=BookingPhoto.PhotoType.BEFORE,
            caption=f'Before — {service.name}',
        )

    booking.status = BookingStatus.IN_PROGRESS
    booking.started_at = timezone.now()
    booking.save(update_fields=['status', 'started_at', 'updated_at'])

    log_action(
        BOOKING_JOB_STARTED,
        f'Started job for booking #{booking.pk} ({booking.contact_full_name}).',
        request=request,
        target_type='booking',
        target_id=booking.pk,
        target_label=f'Booking #{booking.pk} — {booking.contact_full_name}',
        metadata={'services': [s.name for s in services]},
    )

    return JsonResponse({
        'success': True,
        'booking': booking_detail_payload(request, booking),
    })


def _save_signature_image(booking, data_url):
    if not data_url or not data_url.startswith('data:image'):
        return
    booking.completion_signature = data_url
    booking.save(update_fields=['completion_signature', 'updated_at'])


@panel_required
@require_POST
def booking_complete_job_api(request, pk):
    booking = get_object_or_404(Booking, pk=pk)
    if booking.status != BookingStatus.IN_PROGRESS:
        return JsonResponse({'error': 'Start the job before completing it.'}, status=400)

    signed_by_name = request.POST.get('signed_by_name', '').strip()
    signature = request.POST.get('signature', '').strip()
    if not signed_by_name:
        return JsonResponse({'error': 'Customer name is required.'}, status=400)
    if not signature:
        return JsonResponse({'error': 'Customer signature is required.'}, status=400)

    services = list(booking.get_services())
    for service in services:
        field_name = f'after_{service.pk}'
        upload = request.FILES.get(field_name)
        if not upload:
            return JsonResponse(
                {'error': f'After photo required for {service.name}.'},
                status=400,
            )
        BookingPhoto.objects.filter(
            booking=booking,
            service=service,
            photo_type=BookingPhoto.PhotoType.AFTER,
        ).delete()
        BookingPhoto.objects.create(
            booking=booking,
            service=service,
            image=upload,
            photo_type=BookingPhoto.PhotoType.AFTER,
            caption=f'After — {service.name}',
        )

    _save_signature_image(booking, signature)
    booking.signed_by_name = signed_by_name
    booking.status = BookingStatus.COMPLETED
    booking.completed_at = timezone.now()
    booking.save(update_fields=[
        'signed_by_name', 'status', 'completed_at', 'updated_at',
    ])
    send_booking_status_email(booking)

    log_action(
        BOOKING_JOB_COMPLETED,
        f'Completed job for booking #{booking.pk} — signed by {signed_by_name}.',
        request=request,
        target_type='booking',
        target_id=booking.pk,
        target_label=f'Booking #{booking.pk} — {booking.contact_full_name}',
        metadata={
            'signed_by_name': signed_by_name,
            'services': [s.name for s in services],
        },
    )

    return JsonResponse({
        'success': True,
        'booking': booking_detail_payload(request, booking),
    })


@admin_required
@require_POST
def booking_quote_api(request, pk):
    """Preview pricing for a service selection without saving."""
    booking = get_object_or_404(Booking, pk=pk)
    try:
        service_ids = [int(value) for value in request.POST.getlist('service_ids') if value.isdigit()]
    except ValueError:
        return JsonResponse({'error': 'Invalid service selection.'}, status=400)

    if not service_ids:
        return JsonResponse({'error': 'Select at least one service.'}, status=400)

    services = list(Service.objects.filter(pk__in=service_ids, active=True))
    if len(services) != len(set(service_ids)):
        return JsonResponse({'error': 'One or more services are invalid.'}, status=400)

    from bookings.promo import resolve_promo_for_services

    pricing = resolve_promo_for_services(services, booking=booking)
    return JsonResponse({
        'pricing': {
            'subtotal': f"{pricing['subtotal']:.2f}",
            'discount': f"{pricing['discount']:.2f}",
            'total': f"{pricing['total']:.2f}",
            'has_discount': pricing['has_discount'],
            'has_promo': pricing['has_promo'],
            'promo_code': pricing['promo_code'],
            'promo_auto': pricing['promo_auto'],
        },
    })


@panel_required
@require_GET
def booking_services_catalog_api(request):
    services = Service.objects.filter(active=True).order_by('sort_order', 'name')
    return JsonResponse({
        'services': [
            {
                'id': service.pk,
                'name': service.name,
                'description': service.description,
                'price': f'{service.price:.2f}',
                'service_type': service.service_type,
                'exclusive_group': service.exclusive_group,
            }
            for service in services
        ],
        'oven_types': ServiceType.OVEN,
        'addon_types': ServiceType.ADDON,
    })
