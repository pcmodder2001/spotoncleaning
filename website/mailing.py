from accounts.models import CustomUser
from website.models import MailingListSubscriber


def normalize_email(email):
    return (email or '').strip().lower()


def is_on_mailing_list(email):
    email = normalize_email(email)
    if not email:
        return False
    if CustomUser.objects.filter(email__iexact=email, marketing_opt_in=True).exists():
        return True
    return MailingListSubscriber.objects.filter(email=email, active=True).exists()


def subscribe_email(email, *, source='booking', user=None):
    email = normalize_email(email)
    if not email:
        return None
    subscriber, _ = MailingListSubscriber.objects.update_or_create(
        email=email,
        defaults={'active': True, 'source': source or 'booking'},
    )
    if user is not None and getattr(user, 'pk', None) and not user.marketing_opt_in:
        user.marketing_opt_in = True
        user.save(update_fields=['marketing_opt_in'])
    elif user is None:
        CustomUser.objects.filter(email__iexact=email, marketing_opt_in=False).update(
            marketing_opt_in=True,
        )
    return subscriber
