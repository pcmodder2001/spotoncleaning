from decimal import Decimal

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from bookings.models import PromoCode


class PromoError(Exception):
    pass


def normalize_promo_code(code):
    return (code or '').strip().upper()


def _usage_limit_reached(promo):
    return promo.max_uses is not None and promo.times_used >= promo.max_uses


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
    if _usage_limit_reached(promo):
        raise PromoError('That promo code has reached its usage limit.')
    today = timezone.localdate()
    if promo.valid_from and today < promo.valid_from:
        raise PromoError('That promo code is not valid yet.')
    if promo.valid_until and today > promo.valid_until:
        raise PromoError('That promo code has expired.')
    return promo


def apply_promo_to_booking(booking, code):
    """Validate promo and set discount on booking (does not save)."""
    promo = get_valid_promo(code)
    if promo is None:
        booking.promo_code = None
        booking.discount_amount = Decimal('0.00')
        return booking

    subtotal = sum(s.price for s in booking.get_services()) if booking.pk else Decimal('0.00')
    if not subtotal and hasattr(booking, '_pending_service_ids'):
        from services.models import Service
        subtotal = sum(
            s.price for s in Service.objects.filter(pk__in=booking._pending_service_ids)
        )

    discount = promo.calculate_discount(subtotal)
    if discount <= 0:
        raise PromoError(
            f'This code requires a minimum order of £{promo.min_order_amount:.2f}.'
        )

    booking.promo_code = promo
    booking.discount_amount = discount
    return booking


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
