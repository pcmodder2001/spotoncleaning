from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string


def send_notification_email(subject, template_name, context, recipient):
    html_message = render_to_string(template_name, context)
    send_mail(
        subject=subject,
        message='',
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[recipient],
        html_message=html_message,
        fail_silently=False,
    )


def send_registration_email(user):
    send_notification_email(
        subject=f'Welcome to {settings.SITE_NAME}',
        template_name='emails/registration.html',
        context={'user': user, 'site_name': settings.SITE_NAME},
        recipient=user.email,
    )


def send_booking_email(booking, template, subject):
    send_notification_email(
        subject=subject,
        template_name=template,
        context={'booking': booking, 'site_name': settings.SITE_NAME},
        recipient=booking.user.email,
    )


def send_booking_created_email(booking):
    send_booking_email(
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
        send_booking_email(booking, template, f'{subject} - {settings.SITE_NAME}')
