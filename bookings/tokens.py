import base64
import binascii

from django.core.signing import BadSignature, SignatureExpired, TimestampSigner

from bookings.models import Booking, CustomerFollowUp

booking_signer = TimestampSigner(salt='spoton-booking-account')
followup_signer = TimestampSigner(salt='spoton-followup-account')
TOKEN_MAX_AGE = 60 * 60 * 24 * 14  # 14 days

# Backwards-compatible alias used by older imports/tests
signer = booking_signer


def _encode_token(signed_value):
    return base64.urlsafe_b64encode(signed_value.encode('ascii')).decode('ascii').rstrip('=')


def _decode_token(encoded):
    padding = '=' * (-len(encoded) % 4)
    return base64.urlsafe_b64decode((encoded + padding).encode('ascii')).decode('ascii')


def make_booking_account_token(booking):
    """URL-safe token for email links (no colons — those break some proxies/browsers)."""
    return _encode_token(booking_signer.sign(str(booking.pk)))


def make_followup_account_token(followup):
    """URL-safe token for follow-up account setup email links."""
    return _encode_token(followup_signer.sign(str(followup.pk)))


def _signed_value_candidates(token):
    """Accept new base64 tokens and legacy raw signed strings from old emails."""
    if not token:
        return
    yield token
    try:
        yield _decode_token(token)
    except (ValueError, UnicodeDecodeError, binascii.Error):
        pass


def booking_from_account_token(token, max_age=TOKEN_MAX_AGE):
    for raw in _signed_value_candidates(token):
        try:
            booking_pk = int(booking_signer.unsign(raw, max_age=max_age))
        except (BadSignature, SignatureExpired, ValueError):
            continue
        booking = Booking.objects.filter(pk=booking_pk, user__isnull=True).first()
        if booking:
            return booking
    return None


def followup_from_account_token(token, max_age=TOKEN_MAX_AGE):
    for raw in _signed_value_candidates(token):
        try:
            followup_pk = int(followup_signer.unsign(raw, max_age=max_age))
        except (BadSignature, SignatureExpired, ValueError):
            continue
        followup = CustomerFollowUp.objects.filter(pk=followup_pk).exclude(email='').first()
        if followup:
            return followup
    return None
