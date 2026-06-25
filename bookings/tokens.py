from django.core.signing import BadSignature, SignatureExpired, TimestampSigner

from bookings.models import Booking

signer = TimestampSigner(salt='spoton-booking-account')
TOKEN_MAX_AGE = 60 * 60 * 24 * 14  # 14 days


def make_booking_account_token(booking):
    return signer.sign(str(booking.pk))


def booking_from_account_token(token, max_age=TOKEN_MAX_AGE):
    try:
        booking_pk = int(signer.unsign(token, max_age=max_age))
    except (BadSignature, SignatureExpired, ValueError):
        return None
    return Booking.objects.filter(pk=booking_pk, user__isnull=True).first()
