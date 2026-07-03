import logging
from datetime import timedelta

from django.conf import settings
from django.urls import reverse
from django.utils import timezone

from bookings.notifications import get_email_context, send_branded_email
from hr.models import EmployeeInvite

logger = logging.getLogger(__name__)


def invite_valid_days():
    return getattr(settings, 'HR_INVITE_VALID_DAYS', 14)


def create_employee_invite(*, email, invited_by, first_name='', last_name='', job_title='Cleaning technician',
                           employment_type='full_time', start_date=None, hourly_rate=None, personal_message=''):
    email = email.lower().strip()
    expires_at = timezone.now() + timedelta(days=invite_valid_days())
    return EmployeeInvite.objects.create(
        email=email,
        first_name=first_name.strip(),
        last_name=last_name.strip(),
        job_title=job_title.strip() or 'Cleaning technician',
        employment_type=employment_type,
        start_date=start_date,
        hourly_rate=hourly_rate,
        personal_message=personal_message.strip(),
        invited_by=invited_by,
        expires_at=expires_at,
    )


def invite_registration_url(invite):
    path = reverse('accounts:register_invite', kwargs={'token': invite.token})
    return f'{settings.SITE_URL.rstrip("/")}{path}'


def send_employee_invite_email(invite):
    invite_url = invite_registration_url(invite)
    context = get_email_context(
        invite=invite,
        invite_url=invite_url,
        invite_expires=invite.expires_at,
        personal_message=invite.personal_message,
    )
    try:
        send_branded_email(
            subject=f'Join {settings.SITE_NAME} — complete your account setup',
            recipient=invite.email,
            html_template='emails/employee_invite.html',
            context=context,
            plain_message=(
                f'You have been invited to join {settings.SITE_NAME} as {invite.job_title}.\n\n'
                f'Create your account here (link expires {invite.expires_at:%d %B %Y}):\n{invite_url}\n'
            ),
        )
        invite.sent_at = timezone.now()
        invite.save(update_fields=['sent_at'])
        return True
    except Exception:
        logger.exception('Failed to send employee invite to %s', invite.email)
        return False


def accept_invite(invite, user):
    invite.user = user
    invite.accepted_at = timezone.now()
    invite.save(update_fields=['user', 'accepted_at'])


def get_valid_invite(token):
    invite = EmployeeInvite.objects.filter(token=token).select_related('invited_by').first()
    if invite and invite.is_valid:
        return invite
    return None
