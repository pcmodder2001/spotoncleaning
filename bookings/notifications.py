import logging

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags

logger = logging.getLogger(__name__)


def get_email_context(**extra):
    site_url = settings.SITE_URL.rstrip('/')
    return {
        'site_name': settings.SITE_NAME,
        'site_tagline': settings.SITE_TAGLINE,
        'site_url': site_url,
        'site_email': settings.SITE_EMAIL,
        'site_phone': settings.SITE_PHONE,
        'logo_url': f'{site_url}/static/img/logo.png',
        **extra,
    }


def send_notification_email(subject, template_name, context, recipient, *, test=False):
    context = get_email_context(**context)
    html_message = render_to_string(template_name, context)
    plain_message = strip_tags(html_message).strip()
    if test:
        subject = f'[TEST] {subject}'
    try:
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient],
            html_message=html_message,
            fail_silently=False,
        )
        return True
    except Exception:
        logger.exception('Failed to send email to %s: %s', recipient, subject)
        return False


def send_registration_email(user):
    return send_notification_email(
        subject=f'Welcome to {settings.SITE_NAME}',
        template_name='emails/registration.html',
        context={'user': user},
        recipient=user.email,
    )


def send_booking_email(booking, template, subject):
    return send_notification_email(
        subject=subject,
        template_name=template,
        context={'booking': booking},
        recipient=booking.user.email,
    )


def send_test_emails(subject, template_name, context, recipients):
    """Send the same templated email to each recipient. Returns (email, success) pairs."""
    results = []
    for recipient in recipients:
        ok = send_notification_email(
            subject,
            template_name,
            context,
            recipient,
            test=True,
        )
        results.append((recipient, ok))
    return results


def send_booking_created_email(booking):
    return send_booking_email(
        booking,
        'emails/booking_created.html',
        f'Booking Confirmation - {settings.SITE_NAME}',
    )


def send_booking_status_email(booking):
    templates = {
        'confirmed': ('emails/booking_confirmed.html', 'Your booking has been confirmed'),
        'completed': ('emails/booking_completed.html', 'Your booking has been completed'),
        'cancelled': ('emails/booking_cancelled.html', 'Your booking has been cancelled'),
    }
    if booking.status in templates:
        template, subject = templates[booking.status]
        return send_booking_email(booking, template, f'{subject} - {settings.SITE_NAME}')
    return False
