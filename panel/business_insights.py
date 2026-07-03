from accounts.account_types import AccountType
from accounts.models import BusinessProfile


def user_business_summary(user):
    """Read-only business context for a panel user record."""
    if not user or not user.is_business_account:
        return None

    profile = None
    if hasattr(user, 'business_profile'):
        try:
            profile = user.business_profile
        except BusinessProfile.DoesNotExist:
            profile = None

    property_count = getattr(user, 'property_count', None)
    if property_count is None and user.pk:
        property_count = user.properties.count()

    booking_count = getattr(user, 'booking_count', None)
    if booking_count is None and user.pk:
        booking_count = user.bookings.count()

    return {
        'account_type': AccountType.BUSINESS,
        'account_type_label': AccountType.BUSINESS.label,
        'company_name': profile.company_name if profile else '',
        'invoice_email': profile.invoice_email if profile else '',
        'property_count': property_count or 0,
        'booking_count': booking_count or 0,
    }


def booking_business_payload(booking):
    """Business context for a booking (API + templates)."""
    user = booking.user
    if not user or not user.is_business_account:
        return None

    summary = user_business_summary(user)
    payload = {
        **summary,
        'booked_by_name': user.full_name,
        'booked_by_email': user.email,
        'booked_by_phone': user.phone_number or '',
        'user_id': user.pk,
        'user_edit_url': f'/panel/users/{user.pk}/edit/',
    }

    prop = booking.rental_property
    if prop:
        payload['property'] = {
            'id': prop.pk,
            'reference': prop.reference,
            'display_label': prop.display_label,
            'summary': prop.summary,
            'access_instructions': prop.access_instructions,
            'contact_name': prop.contact_name,
            'contact_phone': prop.contact_phone,
        }
    else:
        payload['property'] = None

    return payload
