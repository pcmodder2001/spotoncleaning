from bookings.models import Booking


def attach_guest_bookings_to_user(user, email):
    """Link all guest bookings for this email to the new account."""
    guest_bookings = Booking.objects.filter(
        guest_email__iexact=email,
        user__isnull=True,
    )
    for booking in guest_bookings:
        booking.user = user
        booking.clear_guest_fields()
        booking.save(
            update_fields=[
                'user',
                'guest_email',
                'guest_first_name',
                'guest_last_name',
                'guest_phone',
            ]
        )
