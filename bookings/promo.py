from decimal import Decimal

from django.utils import timezone

from bookings.models import PromoCode


class PromoError(Exception):
    pass


def normalize_promo_code(code):
    return (code or '').strip().upper()


def get_valid_promo(code):
    normalized = normalize_promo_code(code)
    if not normalized:
        return None
    try:
        promo = PromoCode.objects.get(code=normalized)
    except PromoCode.DoesNotExist as exc:
        raise PromoError('That promo code is not valid.') from exc
    if not promo.is_valid_today():
        raise PromoError('That promo code has expired or is no longer available.')
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
    if promo:
        PromoCode.objects.filter(pk=promo.pk).update(times_used=promo.times_used + 1)
