from accounts.account_types import AccountType
from accounts.models import BusinessProfile, Property


def get_business_profile(user):
    if not user.is_authenticated or not user.is_business_account:
        return None
    return BusinessProfile.objects.filter(user=user).first()


def get_properties_for_user(user):
    if not user.is_authenticated or not user.is_business_account:
        return Property.objects.none()
    return Property.objects.filter(user=user)


def get_default_property(user):
    if not user.is_authenticated or not user.is_business_account:
        return None
    address = Property.objects.filter(user=user, is_default=True).first()
    if address:
        return address
    return Property.objects.filter(user=user).first()


def ensure_business_profile(user, *, company_name, invoice_email):
    profile, _created = BusinessProfile.objects.update_or_create(
        user=user,
        defaults={
            'company_name': company_name,
            'invoice_email': invoice_email,
        },
    )
    if user.account_type != AccountType.BUSINESS:
        user.account_type = AccountType.BUSINESS
        user.save(update_fields=['account_type'])
    return profile
