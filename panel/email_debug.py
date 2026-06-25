from datetime import datetime, timedelta

import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.template.loader import render_to_string
from django.utils import timezone

from bookings.models import Booking, BookingStatus, TimeSlot
from bookings.notifications import send_branded_email, send_test_emails
from services.models import Service

User = get_user_model()

logger = logging.getLogger(__name__)


class _SampleServices:
    def __init__(self, services):
        self._services = list(services)

    def all(self):
        return self

    def exists(self):
        return bool(self._services)

    def __iter__(self):
        return iter(self._services)

    def values_list(self, field, flat=False):
        if field == 'name':
            return [service.name for service in self._services]
        if field == 'pk':
            return [service.pk for service in self._services]
        return []


class SampleBooking:
    """Lightweight booking stand-in for email previews when no real booking exists."""

    def __init__(self, user, time_slot, services, status=BookingStatus.PENDING):
        self.pk = 0
        self.user = user
        self.time_slot = time_slot
        self.date = timezone.localdate() + timedelta(days=7)
        self.address_line_1 = '123 Example Street'
        self.address_line_2 = ''
        self.city = 'Wakefield'
        self.postcode = 'WF1 1AA'
        self.notes = 'Sample booking used for email testing.'
        self.status = status
        self._services = _SampleServices(services)
        self.service = services[0] if services else None

    def get_services(self):
        return self._services

    @property
    def service_summary(self):
        names = list(self._services.values_list('name', flat=True))
        return ', '.join(names) if names else 'Standard Oven (with Grill)'

    @property
    def total_price(self):
        return sum(service.price for service in self._services)

    @property
    def full_address(self):
        return f'{self.address_line_1}, {self.city}, {self.postcode}'

    def get_status_display(self):
        return dict(BookingStatus.choices).get(self.status, self.status)


def get_sysadmin_recipients():
    return list(settings.SYSADMIN_EMAILS)


def get_sample_user():
    for email in settings.SYSADMIN_EMAILS:
        user = User.objects.filter(email__iexact=email).first()
        if user:
            return user
    user = User.objects.filter(is_staff=True).first()
    if user:
        return user
    return User(
        email=settings.SYSADMIN_EMAILS[0] if settings.SYSADMIN_EMAILS else 'admin@example.com',
        first_name='Test',
        last_name='User',
    )


def get_sample_booking(status=BookingStatus.PENDING):
    booking = (
        Booking.objects.select_related('user', 'time_slot')
        .prefetch_related('services')
        .order_by('-created_at')
        .first()
    )
    if booking:
        booking.status = status
        return booking

    user = get_sample_user()
    time_slot = TimeSlot.objects.filter(active=True).order_by('time').first()
    if not time_slot:
        time_slot = TimeSlot(time=datetime.strptime('10:00', '%H:%M').time())

    services = list(Service.objects.filter(active=True).order_by('sort_order')[:2])
    if not services:
        services = [
            Service(
                name='Standard Oven (with Grill)',
                description='Sample service',
                price=59,
                active=True,
            )
        ]

    return SampleBooking(user, time_slot, services, status=status)


EMAIL_TEST_TYPES = [
    {
        'id': 'registration',
        'name': 'Registration welcome',
        'description': 'Sent when a customer creates an account.',
        'template': 'emails/registration.html',
    },
    {
        'id': 'booking_created',
        'name': 'Booking confirmation',
        'description': 'Sent when a customer submits a new booking.',
        'template': 'emails/booking_created.html',
    },
    {
        'id': 'booking_confirmed',
        'name': 'Booking confirmed',
        'description': 'Sent when staff confirm a booking.',
        'template': 'emails/booking_confirmed.html',
    },
    {
        'id': 'booking_completed',
        'name': 'Booking completed',
        'description': 'Sent when staff mark a job as completed.',
        'template': 'emails/booking_completed.html',
    },
    {
        'id': 'booking_cancelled',
        'name': 'Booking cancelled',
        'description': 'Sent when a booking is cancelled.',
        'template': 'emails/booking_cancelled.html',
    },
    {
        'id': 'password_reset',
        'name': 'Password reset',
        'description': 'Sent when a user requests a password reset link.',
        'template': 'emails/password_reset.html',
    },
]

EMAIL_TEST_TYPES_BY_ID = {item['id']: item for item in EMAIL_TEST_TYPES}


def get_email_config_summary():
    return {
        'backend': settings.EMAIL_BACKEND.rsplit('.', 1)[-1],
        'host': settings.EMAIL_HOST,
        'port': settings.EMAIL_PORT,
        'use_tls': settings.EMAIL_USE_TLS,
        'use_ssl': getattr(settings, 'EMAIL_USE_SSL', False),
        'from_email': settings.DEFAULT_FROM_EMAIL,
        'host_user': settings.EMAIL_HOST_USER or '—',
    }


def send_test_email(email_type_id):
    email_type = EMAIL_TEST_TYPES_BY_ID.get(email_type_id)
    if not email_type:
        return None, []

    recipients = get_sysadmin_recipients()
    if not recipients:
        return email_type, []

    if email_type_id == 'registration':
        results = send_test_emails(
            f'Welcome to {settings.SITE_NAME}',
            email_type['template'],
            {'user': get_sample_user()},
            recipients,
        )
        return email_type, results

    if email_type_id == 'password_reset':
        user = get_sample_user()
        context = {
            'email': user.email,
            'domain': settings.SITE_URL.replace('https://', '').replace('http://', ''),
            'uid': 'test',
            'user': user,
            'token': 'test-token-not-valid',
            'protocol': 'https' if settings.SITE_URL.startswith('https') else 'http',
        }
        subject = render_to_string('accounts/password_reset_subject.txt', context).strip()
        plain_body = render_to_string('accounts/password_reset_email.html', context)
        results = []
        for recipient in recipients:
            try:
                send_branded_email(
                    subject=f'[TEST] {subject}',
                    recipient=recipient,
                    html_template=email_type['template'],
                    context=context,
                    plain_message=plain_body,
                )
                results.append((recipient, True))
            except Exception:
                logger.exception('Failed to send password reset test email to %s', recipient)
                results.append((recipient, False))
        return email_type, results

    status_map = {
        'booking_created': BookingStatus.PENDING,
        'booking_confirmed': BookingStatus.CONFIRMED,
        'booking_completed': BookingStatus.COMPLETED,
        'booking_cancelled': BookingStatus.CANCELLED,
    }
    subject_map = {
        'booking_created': f'Booking Confirmation - {settings.SITE_NAME}',
        'booking_confirmed': f'Your booking has been confirmed - {settings.SITE_NAME}',
        'booking_completed': f'Your booking has been completed - {settings.SITE_NAME}',
        'booking_cancelled': f'Your booking has been cancelled - {settings.SITE_NAME}',
    }

    booking = get_sample_booking(status=status_map[email_type_id])
    results = send_test_emails(
        subject_map[email_type_id],
        email_type['template'],
        {'booking': booking},
        recipients,
    )
    return email_type, results
