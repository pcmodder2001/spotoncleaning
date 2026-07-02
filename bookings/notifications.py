import logging
import base64
from email.mime.image import MIMEImage
from pathlib import Path
from urllib.parse import urlencode

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.html import strip_tags

from bookings.completion_report import get_completion_report_context
from bookings.models import BookingStatus
from config.static_utils import versioned_static_url

logger = logging.getLogger(__name__)

LOGO_CONTENT_ID = 'spoton-logo'
LOGO_STATIC_PATH = 'img/logo.png'


def get_logo_path():
    return settings.BASE_DIR / 'static' / LOGO_STATIC_PATH


def get_email_context(*, embed_logo=False, **extra):
    site_url = settings.SITE_URL.rstrip('/')
    logo_url = f'cid:{LOGO_CONTENT_ID}' if embed_logo else versioned_static_url(
        LOGO_STATIC_PATH,
        absolute=True,
    )
    return {
        **extra,
        'site_name': settings.SITE_NAME,
        'site_tagline': settings.SITE_TAGLINE,
        'site_url': site_url,
        'site_email': settings.SITE_EMAIL,
        'site_phone': settings.SITE_PHONE,
        'logo_url': logo_url,
    }


def attach_inline_logo(email_message):
    logo_path = get_logo_path()
    if not logo_path.exists():
        logger.warning('Logo file missing for email embedding: %s', logo_path)
        return False

    with logo_path.open('rb') as logo_file:
        mime_image = MIMEImage(logo_file.read(), _subtype='png')
    mime_image.add_header('Content-ID', f'<{LOGO_CONTENT_ID}>')
    mime_image.add_header('Content-Disposition', 'inline', filename='logo.png')
    email_message.attach(mime_image)
    return True


def _attach_inline_file(email_message, file_path, content_id, *, filename='image.jpg'):
    path = Path(file_path)
    if not path.exists():
        logger.warning('Missing inline email attachment: %s', file_path)
        return False
    subtype = 'jpeg' if path.suffix.lower() in ('.jpg', '.jpeg') else 'png'
    with path.open('rb') as image_file:
        mime_image = MIMEImage(image_file.read(), _subtype=subtype)
    mime_image.add_header('Content-ID', f'<{content_id}>')
    mime_image.add_header('Content-Disposition', 'inline', filename=filename)
    email_message.attach(mime_image)
    return True


def _attach_signature_data_url(email_message, data_url, content_id):
    if not data_url or not data_url.startswith('data:image'):
        return False
    try:
        header, encoded = data_url.split(',', 1)
        image_data = base64.b64decode(encoded)
        subtype = 'png' if 'png' in header else 'jpeg'
        mime_image = MIMEImage(image_data, _subtype=subtype)
        mime_image.add_header('Content-ID', f'<{content_id}>')
        mime_image.add_header('Content-Disposition', 'inline', filename='signature.png')
        email_message.attach(mime_image)
        return True
    except Exception:
        logger.exception('Failed to attach signature to completion report email')
        return False


def send_branded_email(subject, recipient, html_template, context=None, *, plain_message='', test=False):
    if test:
        subject = f'[TEST] {subject}'

    context = get_email_context(embed_logo=True, **(context or {}))
    html_message = render_to_string(html_template, context)
    if not plain_message:
        plain_message = strip_tags(html_message).strip()

    email = EmailMultiAlternatives(
        subject=subject,
        body=plain_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[recipient],
    )
    email.attach_alternative(html_message, 'text/html')
    attach_inline_logo(email)
    email.send(fail_silently=False)
    return True


def send_notification_email(subject, template_name, context, recipient, *, test=False):
    try:
        send_branded_email(
            subject=subject,
            recipient=recipient,
            html_template=template_name,
            context=context,
            test=test,
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


def get_booking_email_context(booking):
    context = {'booking': booking}
    if booking.is_guest:
        from bookings.tokens import make_booking_account_token

        token = make_booking_account_token(booking)
        context['account_setup_url'] = (
            f'{settings.SITE_URL.rstrip("/")}'
            f'{reverse("accounts:complete_account")}?{urlencode({"token": token})}'
        )
    return context


def send_booking_email(booking, template, subject):
    return send_notification_email(
        subject=subject,
        template_name=template,
        context=get_booking_email_context(booking),
        recipient=booking.contact_email,
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


def send_booking_updated_email(booking):
    return send_notification_email(
        subject=f'Your booking has been updated — {settings.SITE_NAME}',
        template_name='emails/booking_updated.html',
        context=get_booking_email_context(booking),
        recipient=booking.contact_email,
    )


def send_booking_rescheduled_email(booking, *, needs_confirmation=False):
    context = get_booking_email_context(booking)
    context['needs_confirmation'] = needs_confirmation
    return send_notification_email(
        subject=f'Your appointment has been rescheduled — {settings.SITE_NAME}',
        template_name='emails/booking_rescheduled.html',
        context=context,
        recipient=booking.contact_email,
    )


def send_enquiry_received_email(enquiry):
    return send_notification_email(
        subject=f'We received your message — {settings.SITE_NAME}',
        template_name='emails/enquiry_received.html',
        context={'enquiry': enquiry},
        recipient=enquiry.email,
    )


def send_booking_reminder_email(booking):
    from bookings.reminders import get_booking_reminder_context

    return send_notification_email(
        subject=f'Reminder: your appointment is tomorrow — {settings.SITE_NAME}',
        template_name='emails/booking_reminder.html',
        context=get_booking_reminder_context(booking),
        recipient=booking.contact_email,
    )


def send_booking_status_email(booking):
    if booking.status == BookingStatus.COMPLETED and booking.has_complete_job_workflow():
        return send_booking_completion_report_email(booking)

    templates = {
        'confirmed': ('emails/booking_confirmed.html', 'Your booking has been confirmed'),
        'completed': ('emails/booking_completed.html', 'Your booking has been completed'),
        'cancelled': ('emails/booking_cancelled.html', 'Your booking has been cancelled'),
    }
    if booking.status in templates:
        template, subject = templates[booking.status]
        return send_booking_email(booking, template, f'{subject} - {settings.SITE_NAME}')
    return False


def send_booking_completion_report_email(booking, *, test=False, recipient=None, context=None):
    """Email customer a completion report with photos, pricing, and sign-off."""
    try:
        report_context = context or get_completion_report_context(booking, for_email=True)
        subject = f'Your job completion report — {settings.SITE_NAME}'
        if test:
            subject = f'[TEST] {subject}'

        email_context = get_email_context(embed_logo=True, **report_context)
        html_message = render_to_string('emails/booking_completion_report.html', email_context)
        plain_message = strip_tags(html_message).strip()

        email = EmailMultiAlternatives(
            subject=subject,
            body=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[recipient or booking.contact_email],
        )
        email.attach_alternative(html_message, 'text/html')
        attach_inline_logo(email)

        for row in report_context['service_photos']:
            if row.get('before_path'):
                _attach_inline_file(
                    email,
                    row['before_path'],
                    row['before_cid'],
                    filename=f"before-{row['name']}.jpg",
                )
            if row.get('after_path'):
                _attach_inline_file(
                    email,
                    row['after_path'],
                    row['after_cid'],
                    filename=f"after-{row['name']}.jpg",
                )

        if report_context.get('signature_data_url'):
            _attach_signature_data_url(
                email,
                report_context['signature_data_url'],
                report_context['signature_cid'],
            )

        email.send(fail_silently=False)
        return True
    except Exception:
        logger.exception(
            'Failed to send completion report email for booking #%s',
            getattr(booking, 'pk', '?'),
        )
        return False
