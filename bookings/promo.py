from decimal import Decimal

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from bookings.models import PromoCode
from services.models import Service, ServiceType


class PromoError(Exception):
    pass


class PromoEligibilityError(PromoError):
    pass


def normalize_promo_code(code):
    return (code or '').strip().upper()


def _usage_limit_reached(promo):
    return promo.max_uses is not None and promo.times_used >= promo.max_uses


def count_appliances(services, *, include_addons=False):
    """Count services toward a promo minimum. Main appliances always count; add-ons only when enabled."""
    total = 0
    for service in services:
        if service.service_type == ServiceType.OVEN:
            total += 1
        elif include_addons and service.service_type == ServiceType.ADDON:
            total += 1
    return total


def get_valid_promo(code, **customer):
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
    assert_promo_customer_eligible(promo, **customer)
    return promo


def _authenticated_user(user):
    return bool(user is not None and getattr(user, 'is_authenticated', False) and getattr(user, 'pk', None))


def customer_non_cancelled_booking_count(user, *, exclude_booking_id=None):
    from bookings.models import Booking, BookingStatus

    if not _authenticated_user(user):
        return 0
    queryset = Booking.objects.filter(user=user).exclude(status=BookingStatus.CANCELLED)
    if exclude_booking_id:
        queryset = queryset.exclude(pk=exclude_booking_id)
    return queryset.count()


def assert_promo_customer_eligible(
    promo,
    *,
    user=None,
    email='',
    join_mailing_list=False,
    exclude_booking_id=None,
):
    """Raise PromoEligibilityError if this customer cannot use the promo."""
    from website.mailing import is_on_mailing_list

    logged_in = _authenticated_user(user)
    email = (email or getattr(user, 'email', '') or '').strip()

    if promo.requires_account or promo.first_order_only:
        if not logged_in:
            raise PromoEligibilityError(
                'Log in or create an account to use this code.'
            )
    if promo.first_order_only and logged_in:
        if customer_non_cancelled_booking_count(user, exclude_booking_id=exclude_booking_id) > 0:
            raise PromoEligibilityError('This code is for your first booking only.')

    if promo.requires_signup_or_mailing_list:
        has_account = logged_in
        on_list = is_on_mailing_list(email) or bool(getattr(user, 'marketing_opt_in', False))
        joining_now = bool(join_mailing_list)
        if not (has_account or on_list or joining_now):
            raise PromoEligibilityError(
                'Create an account or join our mailing list to use this code.'
            )
    return True


def customer_qualifies_for_promo(promo, **customer):
    try:
        assert_promo_customer_eligible(promo, **customer)
        return True
    except PromoEligibilityError:
        return False


def bookings_using_promo(promo):
    from django.db.models import Q

    from bookings.models import Booking

    return (
        Booking.objects.filter(
            Q(promo_code=promo) | Q(applied_promos__contains=[{'id': promo.pk}])
        )
        .select_related('user', 'time_slot')
        .prefetch_related('services')
        .order_by('-date', '-pk')
        .distinct()
    )


def get_qualifying_auto_promos(services, **customer):
    """All active auto promos that qualify for the selected services."""
    if not services:
        return []

    candidates = PromoCode.objects.filter(
        active=True,
        auto_apply=True,
        min_appliance_count__isnull=False,
    ).order_by('-min_appliance_count', '-discount_value')

    return [
        promo for promo in candidates
        if promo.qualifies_for_services(services) and customer_qualifies_for_promo(promo, **customer)
    ]


def get_auto_promo_for_services(services, **customer):
    """Best matching active auto promo for the selected services, if any."""
    promos = select_auto_promos(services, **customer)
    return promos[0] if promos else None


def select_auto_promos(services, **customer):
    """
    Choose which auto promos to apply.

    Stackable autos can all apply together. Non-stackable autos are exclusive —
    only the best one is used, and it cannot mix with stackables.
    """
    qualifying = get_qualifying_auto_promos(services, **customer)
    if not qualifying:
        return []

    stackable = [p for p in qualifying if p.stackable]
    exclusive = [p for p in qualifying if not p.stackable]

    if exclusive and not stackable:
        return [exclusive[0]]
    if stackable and not exclusive:
        return stackable

    # Both kinds qualify — pick whichever bundle saves more on the current subtotal.
    subtotal = _services_subtotal(services)
    exclusive_discount = _total_discount_for_promos([exclusive[0]], subtotal)
    stackable_discount = _total_discount_for_promos(stackable, subtotal)
    if exclusive_discount >= stackable_discount:
        return [exclusive[0]]
    return stackable


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


def _discount_rows_for_promos(promos, subtotal):
    """Apply promos sequentially on the remaining balance; return rows + total."""
    remaining = Decimal(subtotal)
    rows = []
    total = Decimal('0.00')
    for promo in promos:
        if remaining <= 0:
            break
        amount = promo.calculate_discount(remaining)
        if amount <= 0:
            continue
        amount = min(amount, remaining).quantize(Decimal('0.01'))
        rows.append({
            'id': promo.pk,
            'code': promo.code,
            'description': promo.description or '',
            'discount': amount,
            'auto': bool(promo.auto_apply),
            'stackable': bool(promo.stackable),
        })
        total += amount
        remaining -= amount
    return rows, total.quantize(Decimal('0.01'))


def _total_discount_for_promos(promos, subtotal):
    _, total = _discount_rows_for_promos(promos, subtotal)
    return total


def build_pricing_payload(*, subtotal, discount, promo=None, promos=None, rows=None):
    total = max(Decimal('0.00'), subtotal - discount)
    promo_list = promos or ([promo] if promo else [])
    if rows is None and promo_list:
        rows, discount = _discount_rows_for_promos(promo_list, subtotal)
        total = max(Decimal('0.00'), subtotal - discount)

    primary = promo_list[0] if promo_list else promo
    return {
        'subtotal': subtotal.quantize(Decimal('0.01')),
        'discount': discount.quantize(Decimal('0.01')),
        'total': total.quantize(Decimal('0.01')),
        'has_discount': discount > 0,
        'has_promo': bool(promo_list and discount > 0),
        'promo_code': primary.code if primary else None,
        'promo_description': primary.description if primary else '',
        'promo_auto': bool(primary and primary.auto_apply),
        'promos': [
            {
                'code': row['code'],
                'description': row.get('description', ''),
                'discount': str(row['discount'].quantize(Decimal('0.01'))),
                'auto': bool(row.get('auto')),
                'stackable': bool(row.get('stackable')),
            }
            for row in (rows or [])
        ],
        'message': combined_promo_message(rows or [], discount),
    }


def combined_promo_message(rows, discount):
    if not rows or discount <= 0:
        return ''
    if len(rows) == 1:
        row = rows[0]
        if row.get('description'):
            return f'{row["description"]} — save £{discount:.2f}'
        if row.get('auto'):
            return f'{row["code"]} applied — save £{discount:.2f}'
        return f'{row["code"]} applied — save £{discount:.2f}'
    codes = ', '.join(row['code'] for row in rows)
    return f'{codes} combined — save £{discount:.2f}'


def resolve_promos_for_services(services, *, booking=None, manual_code=None, **customer):
    """
    Resolve which promos apply and the combined discount.

    Stacking rules:
    - A manual code and an auto promo combine only when both are stackable.
    - Multiple stackable autos can combine with each other.
    - Non-stackable promos are exclusive.
    """
    if booking is not None:
        customer.setdefault('user', getattr(booking, 'user', None))
        customer.setdefault('email', getattr(booking, 'contact_email', '') or '')
        customer.setdefault('exclude_booking_id', getattr(booking, 'pk', None))

    subtotal = _services_subtotal(services)
    selected = []

    if manual_code:
        manual = get_valid_promo(manual_code, **customer)
        if not manual.qualifies_for_services(services):
            raise PromoError('This promo does not apply to the selected services.')
        calculate_promo_discount(manual, subtotal)
        # Stackable auto offers (e.g. multi-appliance) stay applied with a typed code.
        autos = [
            auto for auto in select_auto_promos(services, **customer)
            if auto.stackable and auto.pk != manual.pk
        ]
        selected = autos + [manual]
    elif booking and booking.promo_code_id and not booking.promo_code.auto_apply:
        manual = booking.promo_code
        autos = [
            auto for auto in select_auto_promos(services, **customer)
            if auto.stackable and auto.pk != manual.pk
        ]
        selected = autos + [manual]
        rows, discount = _discount_rows_for_promos(selected, subtotal)
        if discount <= 0:
            selected = select_auto_promos(services, **customer)
    elif booking and booking.discount_amount and not booking.promo_code_id and not booking.applied_promos:
        discount = min(booking.discount_amount, subtotal)
        return build_pricing_payload(subtotal=subtotal, discount=discount, promo=None, promos=[], rows=[])
    else:
        selected = select_auto_promos(services, **customer)

    rows, discount = _discount_rows_for_promos(selected, subtotal)
    # Drop zero-discount promos from selection
    kept_ids = {row['id'] for row in rows}
    selected = [promo for promo in selected if promo.pk in kept_ids]
    return build_pricing_payload(
        subtotal=subtotal,
        discount=discount,
        promo=selected[0] if selected else None,
        promos=selected,
        rows=rows,
    )


def resolve_promo_for_services(services, *, booking=None, manual_code=None, **customer):
    """Backward-compatible alias."""
    return resolve_promos_for_services(
        services, booking=booking, manual_code=manual_code, **customer
    )


def _apply_pricing_to_booking(booking, pricing, promos):
    booking.discount_amount = pricing['discount']
    by_code = {promo.code: promo for promo in promos}
    booking.applied_promos = [
        {
            'id': by_code[row['code']].pk,
            'code': row['code'],
            'description': row.get('description', ''),
            'discount': row['discount'],
            'auto': bool(row.get('auto')),
            'stackable': bool(row.get('stackable')),
        }
        for row in pricing.get('promos', [])
        if row['code'] in by_code
    ]
    # Prefer a customer-entered (non-auto) code as the primary FK for display.
    primary = next((p for p in promos if not p.auto_apply), None) or (promos[0] if promos else None)
    booking.promo_code = primary
    return booking


def _promos_from_pricing(pricing):
    if not pricing.get('has_promo'):
        return []
    codes = [row['code'] for row in pricing.get('promos', [])]
    by_code = {p.code: p for p in PromoCode.objects.filter(code__in=codes)}
    return [by_code[code] for code in codes if code in by_code]


def refresh_booking_promo(booking, services=None, *, manual_code=None):
    """Update promo_code and discount_amount on booking (does not save)."""
    if booking.pricing_is_locked:
        return booking

    if services is None:
        services = list(booking.get_services())

    if manual_code is not None:
        return apply_promo_to_booking(booking, manual_code)

    pricing = resolve_promos_for_services(services, booking=booking, **{
        'user': getattr(booking, 'user', None),
        'email': getattr(booking, 'contact_email', '') or '',
        'exclude_booking_id': getattr(booking, 'pk', None),
    })
    promos = _promos_from_pricing(pricing)

    if booking.discount_amount and not booking.promo_code_id and not booking.applied_promos and not pricing['has_promo']:
        subtotal = _booking_subtotal(booking, services)
        if booking.discount_amount > subtotal:
            booking.discount_amount = subtotal
        return booking

    return _apply_pricing_to_booking(booking, pricing, promos)


def apply_promo_to_booking(booking, code):
    """Validate promo and set discount on booking (does not save)."""
    services = list(booking.get_services()) if booking.pk else []
    if not services and hasattr(booking, '_pending_service_ids'):
        services = list(Service.objects.filter(pk__in=booking._pending_service_ids))

    if not code:
        pricing = resolve_promos_for_services(services, booking=booking)
        return _apply_pricing_to_booking(booking, pricing, _promos_from_pricing(pricing))

    pricing = resolve_promos_for_services(services, booking=booking, manual_code=code)
    return _apply_pricing_to_booking(booking, pricing, _promos_from_pricing(pricing))


def apply_auto_promo_to_booking(booking, services):
    """Apply matching auto promo(s) for services (does not save)."""
    pricing = resolve_promos_for_services(services, booking=booking)
    return _apply_pricing_to_booking(booking, pricing, _promos_from_pricing(pricing))


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


def record_promos_use(promos):
    """Record usage for one or more promos."""
    seen = set()
    for promo in promos or []:
        promo_id = promo.pk if isinstance(promo, PromoCode) else int(promo)
        if promo_id in seen:
            continue
        seen.add(promo_id)
        record_promo_use(promo_id)


def release_promo_use(promo):
    """Return a promo use when a booking with that code is cancelled."""
    if not promo:
        return
    promo_id = promo.pk if isinstance(promo, PromoCode) else promo
    PromoCode.objects.filter(pk=promo_id, times_used__gt=0).update(
        times_used=F('times_used') - 1,
    )


def release_booking_promos(booking):
    """Release usage for every promo attached to a booking."""
    for promo_id in booking.applied_promo_ids():
        release_promo_use(promo_id)


def sync_promo_times_used(promo=None):
    """Align times_used with non-cancelled bookings (for backfill/repair)."""
    from bookings.models import Booking, BookingStatus

    promos = PromoCode.objects.all()
    if promo is not None:
        promo_id = promo.pk if isinstance(promo, PromoCode) else promo
        promos = promos.filter(pk=promo_id)

    for row in promos:
        by_fk = (
            Booking.objects.filter(promo_code=row)
            .exclude(status=BookingStatus.CANCELLED)
            .values_list('pk', flat=True)
        )
        by_json = (
            Booking.objects.exclude(status=BookingStatus.CANCELLED)
            .exclude(applied_promos=[])
            .filter(applied_promos__contains=[{'id': row.pk}])
            .values_list('pk', flat=True)
        )
        count = len(set(list(by_fk) + list(by_json)))
        if row.times_used != count:
            PromoCode.objects.filter(pk=row.pk).update(times_used=count)
