"""Authorised access to booking job photos (production does not expose /media/ publicly)."""

from urllib.parse import urlencode

from django.urls import reverse


def can_view_booking_photo(request, booking, *, access_token='') -> bool:
    user = getattr(request, 'user', None)
    if user and user.is_authenticated:
        if getattr(user, 'can_access_panel', False):
            return True
        if booking.user_id and booking.user_id == user.id:
            return True
    if access_token:
        from bookings.completion_report import booking_from_completion_report_token
        if booking_from_completion_report_token(access_token) == booking:
            return True
    return False


def booking_photo_url(request, booking, photo, *, access_token='') -> str:
    if not photo or not request:
        return ''
    path = reverse(
        'bookings:job_photo',
        kwargs={'pk': booking.pk, 'photo_pk': photo.pk},
    )
    url = request.build_absolute_uri(path)
    if access_token:
        url = f'{url}?{urlencode({"token": access_token})}'
    return url
