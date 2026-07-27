from decimal import Decimal

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from bookings.models import PromoCode
from services.models import Service, ServiceType


class PromoError(Exception):
    pass


def normalize_promo_code(code):
    return (code or '').strip().upper()


def _usage_limit_reached(promo):
    return promo.max_uses is not None and promo.times_used >= promo.max_uses


def count_appliances(services):
    return sum(1 for service in services if service.service_type == ServiceType.OVEN)


def get_valid_promo(code):
    normalized = normalize_promo_code(code)
    if not normalized:
        return None
    try:
        promo = PromoCode.objects.get(code=normalized)
    except PromoCode.DoesNotExist as exc:
        raise PromoError('That promo code is not valid.') from exc

    if not promo.active:
        raise PromoError('That promo code is no longer active.')
    if promo.auto_apply:
        raise PromoError('That promotion is applied automatically when you qualify.')
    if _usage_limit_reached(promo):
        raise PromoError('That promo code has reached its usage limit.')
    today = timezone.localdate()
    if promo.valid_from and today < promo.valid_from:
        raise PromoError('That promo code is not valid yet.')
    if promo.valid_until and today > promo.valid_until:
        raise PromoError('That promo code has expired.')
    return promo


def get_auto_promo_for_services(services):
    """Best matching active auto promo for the selected services, if any."""
    if not services:
        return None

    candidates = PromoCode.objects.filter(
        active=True,
        auto_apply=True,
        min_appliance_count__isnull=False,
    ).order_by('-min_appliance_count', '-discount_value')

    for promo in candidates:
        if promo.qualifies_for_services(services):
            return promo
    return None


def _booking_subtotal(booking, services):
    if booking.pk and (booking.subtotal or booking.service_line_items):
        return booking.total_price
    return sum(service.price for service in services)


def _services_subtotal(services):
    return sum(service.price for service in services)


def calculate_promo_discount(promo, subtotal):
    discount = promo.calculate_discount(subtotal)
    if discount <= 0:
        raise PromoError(
            f'This code requires a minimum order of £{promo.min_order_amount:.2f}.'
        )
    return discount


def build_pricing_payload(*, subtotal, discount, promo=None):
    total = max(Decimal('0.00'), subtotal - discount)
    return {
        'subtotal': subtotal.quantize(Decimal('0.01')),
        'discount': discount.quantize(Decimal('0.01')),
        'total': total.quantize(Decimal('0.01')),
        'has_discount': discount > 0,
        'has_promo': bool(promo and discount),
        'promo_code': promo.code if promo else None,
        'promo_description': promo.description if promo else '',
        'promo_auto': bool(promo and promo.auto_apply),
    }


def resolve_promo_for_services(services, *, booking=None, manual_code=None):
    """Pick promo + discount for a service selection without mutating a booking."""
    subtotal = _services_subtotal(services)
    promo = None
    discount = Decimal('0.00')

    if manual_code:
        promo = get_valid_promo(manual_code)
        if not promo.qualifies_for_services(services):
            raise PromoError('This promo does not apply to the selected services.')
        discount = calculate_promo_discount(promo, subtotal)
    elif booking and booking.promo_code_id and not booking.promo_code.auto_apply:
        promo = booking.promo_code
        discount = promo.calculate_discount(subtotal)
        if discount <= 0:
            promo = None
            discount = Decimal('0.00')
    elif booking and booking.discount_amount and not booking.promo_code_id:
        discount = min(booking.discount_amount, subtotal)
    else:
        promo = get_auto_promo_for_services(services)
        if promo:
            discount = promo.calculate_discount(subtotal)

    return build_pricing_payload(subtotal=subtotal, discount=discount, promo=promo)


def refresh_booking_promo(booking, services=None, *, manual_code=None):
    """Update promo_code and discount_amount on booking (does not save)."""
    if booking.pricing_is_locked:
        return booking

    if services is None:
        services = list(booking.get_services())

    subtotal = _booking_subtotal(booking, services)

    if manual_code is not None:
        return apply_promo_to_booking(booking, manual_code)

    if manual_code is None and booking.promo_code_id and not booking.promo_code.auto_apply:
        discount = booking.promo_code.calculate_discount(subtotal)
        if discount <= 0:
            booking.promo_code = None
            booking.discount_amount = Decimal('0.00')
        else:
            booking.discount_amount = discount
        return booking

    if booking.discount_amount and not booking.promo_code_id:
        if booking.discount_amount > subtotal:
            booking.discount_amount = subtotal
        return booking

    auto_promo = get_auto_promo_for_services(services)
    if auto_promo:
        booking.promo_code = auto_promo
        booking.discount_amount = auto_promo.calculate_discount(subtotal)
        return booking

    if booking.promo_code_id and booking.promo_code.auto_apply:
        booking.promo_code = None
    booking.discount_amount = Decimal('0.00')
    return booking


def apply_promo_to_booking(booking, code):
    """Validate promo and set discount on booking (does not save)."""
    promo = get_valid_promo(code)
    if promo is None:
        booking.promo_code = None
        booking.discount_amount = Decimal('0.00')
        return booking

    services = list(booking.get_services()) if booking.pk else []
    if not services and hasattr(booking, '_pending_service_ids'):
        services = list(Service.objects.filter(pk__in=booking._pending_service_ids))

    subtotal = _booking_subtotal(booking, services) if services else Decimal('0.00')
    if not subtotal and hasattr(booking, '_pending_service_ids'):
        subtotal = sum(
            service.price
            for service in Service.objects.filter(pk__in=booking._pending_service_ids)
        )

    if services and not promo.qualifies_for_services(services):
        raise PromoError('This promo does not apply to the selected services.')

    discount = calculate_promo_discount(promo, subtotal)
    booking.promo_code = promo
    booking.discount_amount = discount
    return booking


def apply_auto_promo_to_booking(booking, services):
    """Apply the best auto promo for services (does not save)."""
    auto_promo = get_auto_promo_for_services(services)
    if not auto_promo:
        booking.promo_code = None
        booking.discount_amount = Decimal('0.00')
        return booking

    subtotal = sum(service.price for service in services)
    booking.promo_code = auto_promo
    booking.discount_amount = auto_promo.calculate_discount(subtotal)
    return booking


def auto_promo_message(promo, discount):
    if promo.description:
        return f'{promo.description} — save £{discount:.2f}'
    if promo.discount_type == PromoCode.DiscountType.PERCENT:
        return f'{promo.discount_value:.0f}% multi-appliance discount applied — save £{discount:.2f}'
    return f'{promo.code} applied — save £{discount:.2f}'


def record_promo_use(promo):
    """Atomically increment promo usage when a booking is saved."""
    if not promo:
        return
    promo_id = promo.pk if isinstance(promo, PromoCode) else promo
    with transaction.atomic():
        locked = PromoCode.objects.select_for_update().get(pk=promo_id)
        if _usage_limit_reached(locked):
            raise PromoError('That promo code has reached its usage limit.')
        PromoCode.objects.filter(pk=promo_id).update(times_used=F('times_used') + 1)


def release_promo_use(promo):
    """Return a promo use when a booking with that code is cancelled."""
    if not promo:
        return
    promo_id = promo.pk if isinstance(promo, PromoCode) else promo
    PromoCode.objects.filter(pk=promo_id, times_used__gt=0).update(
        times_used=F('times_used') - 1,
    )


def sync_promo_times_used(promo=None):
    """Align times_used with non-cancelled bookings (for backfill/repair)."""
    from bookings.models import Booking, BookingStatus

    promos = PromoCode.objects.all()
    if promo is not None:
        promo_id = promo.pk if isinstance(promo, PromoCode) else promo
        promos = promos.filter(pk=promo_id)

    for row in promos:
        count = (
            Booking.objects.filter(promo_code=row)
            .exclude(status=BookingStatus.CANCELLED)
            .count()
        )
        if row.times_used != count:
            PromoCode.objects.filter(pk=row.pk).update(times_used=count)
