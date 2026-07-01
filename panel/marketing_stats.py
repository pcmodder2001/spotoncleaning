from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

from bookings.models import Booking, BookingStatus
from website.models import ContactMessage
from website.tracking import FACEBOOK_SOURCE_TOKENS, attribution_label, is_facebook_attribution


def _facebook_attribution_q():
    q = Q()
    q |= Q(marketing_attribution__has_key='fbclid') & ~Q(marketing_attribution__fbclid='')
    for token in FACEBOOK_SOURCE_TOKENS:
        q |= Q(marketing_attribution__utm_source__icontains=token)
    return q


def get_marketing_dashboard_context(days=30):
    since = timezone.now() - timedelta(days=days)
    facebook_q = _facebook_attribution_q()

    bookings_recent = Booking.objects.filter(created_at__gte=since).exclude(
        status=BookingStatus.CANCELLED,
    )
    enquiries_recent = ContactMessage.objects.filter(created_at__gte=since)

    facebook_bookings = bookings_recent.filter(facebook_q)
    facebook_enquiries = enquiries_recent.filter(facebook_q)

    recent_facebook_bookings = list(
        facebook_bookings.select_related('time_slot').order_by('-created_at')[:10]
    )
    recent_facebook_enquiries = list(facebook_enquiries.order_by('-created_at')[:10])

    for booking in recent_facebook_bookings:
        booking.source_label = attribution_label(booking.marketing_attribution)
    for enquiry in recent_facebook_enquiries:
        enquiry.source_label = attribution_label(enquiry.marketing_attribution)

    return {
        'days': days,
        'bookings_total': bookings_recent.count(),
        'bookings_facebook': facebook_bookings.count(),
        'enquiries_total': enquiries_recent.count(),
        'enquiries_facebook': facebook_enquiries.count(),
        'recent_facebook_bookings': recent_facebook_bookings,
        'recent_facebook_enquiries': recent_facebook_enquiries,
    }
