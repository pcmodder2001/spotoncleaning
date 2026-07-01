from bookings.models import Booking, BookingStatus
from bookings.routing import is_valid_uk_postcode, normalize_postcode

from .models import SavedAddress


def import_addresses_from_bookings(user):
    """Create saved addresses from past bookings when the user has none yet."""
    if SavedAddress.objects.filter(user=user).exists():
        return 0

    bookings = (
        Booking.objects.filter(user=user)
        .exclude(status=BookingStatus.CANCELLED)
        .order_by('-date', '-created_at')
    )
    seen = set()
    created = 0
    for booking in bookings:
        postcode = normalize_postcode(booking.postcode)
        key = (
            booking.address_line_1.strip().lower(),
            postcode,
        )
        if key in seen:
            continue
        seen.add(key)
        SavedAddress.objects.create(
            user=user,
            label='Home' if created == 0 else '',
            address_line_1=booking.address_line_1,
            address_line_2=booking.address_line_2 or '',
            city=booking.city,
            postcode=postcode,
            is_default=(created == 0),
        )
        created += 1
    return created


def get_default_saved_address(user):
    if not user.is_authenticated:
        return None
    address = SavedAddress.objects.filter(user=user, is_default=True).first()
    if address:
        return address
    return SavedAddress.objects.filter(user=user).first()


def get_saved_addresses_for_user(user):
    if not user.is_authenticated:
        return SavedAddress.objects.none()
    return SavedAddress.objects.filter(user=user)


def save_address_for_user(user, *, label='', address_line_1, address_line_2='', city, postcode, is_default=False):
    postcode = normalize_postcode(postcode)
    existing = SavedAddress.objects.filter(
        user=user,
        address_line_1__iexact=address_line_1.strip(),
        postcode=postcode,
    ).first()
    if existing:
        if is_default and not existing.is_default:
            existing.is_default = True
            existing.save(update_fields=['is_default', 'updated_at'])
        return existing, False

    if is_default or not SavedAddress.objects.filter(user=user).exists():
        is_default = True

    address = SavedAddress.objects.create(
        user=user,
        label=label.strip(),
        address_line_1=address_line_1.strip(),
        address_line_2=(address_line_2 or '').strip(),
        city=city.strip(),
        postcode=postcode,
        is_default=is_default,
    )
    return address, True
