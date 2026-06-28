"""Job completion report — context, tokens, and URLs."""

from __future__ import annotations

import base64
import binascii

from django.conf import settings
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
from django.urls import reverse
from urllib.parse import urlencode

from bookings.models import Booking, BookingPhoto, BookingStatus

completion_report_signer = TimestampSigner(salt='spoton-completion-report')
COMPLETION_REPORT_MAX_AGE = 60 * 60 * 24 * 365  # 1 year


def _encode_token(signed_value: str) -> str:
    return base64.urlsafe_b64encode(signed_value.encode('ascii')).decode('ascii').rstrip('=')


def _decode_token(encoded: str) -> str:
    padding = '=' * (-len(encoded) % 4)
    return base64.urlsafe_b64decode((encoded + padding).encode('ascii')).decode('ascii')


def _signed_value_candidates(token: str):
    if not token:
        return
    yield token
    try:
        yield _decode_token(token)
    except (ValueError, UnicodeDecodeError, binascii.Error):
        pass


def make_completion_report_token(booking) -> str:
    return _encode_token(completion_report_signer.sign(str(booking.pk)))


def booking_from_completion_report_token(token: str, max_age=COMPLETION_REPORT_MAX_AGE):
    for raw in _signed_value_candidates(token):
        try:
            booking_pk = int(completion_report_signer.unsign(raw, max_age=max_age))
        except (BadSignature, SignatureExpired, ValueError):
            continue
        booking = Booking.objects.filter(pk=booking_pk, status=BookingStatus.COMPLETED).first()
        if booking:
            return booking
    return None


def _media_absolute_url(request, file_field):
    if not file_field:
        return ''
    if request:
        return request.build_absolute_uri(file_field.url)
    site_url = settings.SITE_URL.rstrip('/')
    media_url = settings.MEDIA_URL.lstrip('/')
    return f'{site_url}/{media_url}{file_field.name}'


def _photo_row(booking, service, *, request=None, for_email=False):
    before = booking.photos.filter(
        service=service,
        photo_type=BookingPhoto.PhotoType.BEFORE,
    ).first()
    after = booking.photos.filter(
        service=service,
        photo_type=BookingPhoto.PhotoType.AFTER,
    ).first()

    before_cid = f'job-before-{booking.pk}-{service.pk}'
    after_cid = f'job-after-{booking.pk}-{service.pk}'

    row = {
        'name': service.name,
        'before_url': _media_absolute_url(request, before.image if before else None),
        'after_url': _media_absolute_url(request, after.image if after else None),
        'before_cid': before_cid,
        'after_cid': after_cid,
        'before_path': before.image.path if before and before.image else None,
        'after_path': after.image.path if after and after.image else None,
    }
    if for_email:
        row['before_url'] = f'cid:{before_cid}' if row['before_path'] else ''
        row['after_url'] = f'cid:{after_cid}' if row['after_path'] else ''
    return row


def get_completion_report_url(booking, *, request=None) -> str:
    token = make_completion_report_token(booking)
    path = reverse('bookings:completion_report', kwargs={'pk': booking.pk})
    query = urlencode({'token': token})
    if request:
        return f'{request.build_absolute_uri(path)}?{query}'
    return f'{settings.SITE_URL.rstrip("/")}{path}?{query}'


def get_completion_report_context(booking, *, request=None, for_email=False):
    service_photos = [
        _photo_row(booking, service, request=request, for_email=for_email)
        for service in booking.get_services()
    ]
    signature_url = ''
    signature_cid = f'job-signature-{booking.pk}'
    if booking.completion_signature:
        if for_email and booking.completion_signature.startswith('data:image'):
            signature_url = f'cid:{signature_cid}'
        else:
            signature_url = booking.completion_signature

    return {
        'booking': booking,
        'service_photos': service_photos,
        'signed_by_name': booking.signed_by_name,
        'completed_at': booking.completed_at,
        'signature_url': signature_url,
        'signature_cid': signature_cid,
        'signature_data_url': booking.completion_signature,
        'report_url': get_completion_report_url(booking, request=request),
        'total_paid': booking.discounted_total,
        'has_promo': booking.has_promo,
        'promo_code': booking.promo_code.code if booking.promo_code_id else '',
        'discount_amount': booking.discount_amount,
        'subtotal': booking.total_price,
    }


def get_sample_completion_report_context():
    """Fallback preview context when no completed booking with photos exists."""
    from panel.email_debug import get_sample_booking

    booking = (
        Booking.objects.filter(status=BookingStatus.COMPLETED)
        .select_related('time_slot', 'promo_code', 'user')
        .prefetch_related('services', 'photos')
        .order_by('-completed_at')
        .first()
    )
    if booking and booking.has_complete_job_workflow():
        return get_completion_report_context(booking, for_email=True)

    booking = get_sample_booking(status=BookingStatus.COMPLETED)
    booking.signed_by_name = getattr(booking, 'signed_by_name', None) or 'Jane Sample'
    booking.completion_signature = (
        'data:image/svg+xml;base64,'
        + base64.b64encode(
            b'<svg xmlns="http://www.w3.org/2000/svg" width="200" height="60">'
            b'<path d="M10 40 Q50 5 190 35" stroke="#0f172a" stroke-width="2" fill="none"/>'
            b'</svg>'
        ).decode()
    )

    def _placeholder(label: str) -> str:
        svg = (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="400" height="300" fill="#e2e8f0">'
            f'<text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle" '
            f'fill="#64748b" font-family="sans-serif" font-size="16">{label}</text></svg>'
        )
        return 'data:image/svg+xml;base64,' + base64.b64encode(svg.encode()).decode()

    service_photos = []
    for service in booking.get_services():
        service_photos.append({
            'name': service.name,
            'before_url': _placeholder('Before (sample)'),
            'after_url': _placeholder('After (sample)'),
            'before_cid': '',
            'after_cid': '',
            'before_path': None,
            'after_path': None,
        })

    return {
        'booking': booking,
        'service_photos': service_photos,
        'signed_by_name': booking.signed_by_name,
        'completed_at': getattr(booking, 'completed_at', None),
        'signature_url': booking.completion_signature,
        'signature_cid': '',
        'signature_data_url': booking.completion_signature,
        'report_url': f'{settings.SITE_URL.rstrip("/")}/bookings/0/job-report/?token=sample',
        'total_paid': booking.total_price,
        'has_promo': False,
        'promo_code': '',
        'discount_amount': 0,
        'subtotal': booking.total_price,
        'is_sample': True,
    }
