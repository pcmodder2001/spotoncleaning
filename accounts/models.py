from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.exceptions import PermissionDenied
from django.db import models
from django.utils import timezone

from accounts.account_types import AccountType
from accounts.roles import UserRole


class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('Email address is required.')
        email = self.normalize_email(email)
        role = extra_fields.get('role', UserRole.STANDARD)
        extra_fields.setdefault('is_staff', role in (UserRole.ENGINEER, UserRole.ADMIN))
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('role', UserRole.ADMIN)
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        return self.create_user(email, password, **extra_fields)


class CustomUser(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    phone_number = models.CharField(max_length=20, blank=True)
    account_type = models.CharField(
        max_length=20,
        choices=AccountType.choices,
        default=AccountType.PERSONAL,
    )
    role = models.CharField(
        max_length=20,
        choices=UserRole.choices,
        default=UserRole.STANDARD,
    )
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = CustomUserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']

    class Meta:
        ordering = ['-date_joined']

    def __str__(self):
        return self.email

    @property
    def full_name(self):
        return f'{self.first_name} {self.last_name}'.strip()

    @property
    def is_business_account(self):
        return self.account_type == AccountType.BUSINESS

    @property
    def is_sysadmin(self):
        return self.email.lower().strip() in settings.SYSADMIN_EMAILS

    @property
    def can_access_panel(self):
        if self.is_sysadmin:
            return True
        return self.role in (UserRole.ENGINEER, UserRole.ADMIN)

    @property
    def can_manage_site(self):
        if self.is_sysadmin:
            return True
        return self.role == UserRole.ADMIN

    @property
    def role_display(self):
        if self.is_sysadmin:
            return 'System administrator'
        return self.get_role_display()

    def sync_staff_flag(self):
        if self.is_sysadmin or self.role in (UserRole.ENGINEER, UserRole.ADMIN):
            self.is_staff = True
        else:
            self.is_staff = False

    def save(self, *args, **kwargs):
        self.sync_staff_flag()
        super().save(*args, **kwargs)

    def delete(self, using=None, keep_parents=False):
        if self.is_sysadmin:
            raise PermissionDenied('This system administrator account cannot be deleted.')
        super().delete(using=using, keep_parents=keep_parents)


class SavedAddress(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='saved_addresses',
    )
    label = models.CharField(
        max_length=50,
        blank=True,
        help_text='Optional name, e.g. Home or Work.',
    )
    address_line_1 = models.CharField(max_length=255)
    address_line_2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100)
    postcode = models.CharField(max_length=10)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_default', '-updated_at']
        verbose_name_plural = 'Saved addresses'

    def __str__(self):
        label = self.display_label
        return f'{label} ({self.user.email})'

    @property
    def display_label(self):
        if self.label:
            return self.label
        return self.address_line_1

    @property
    def summary(self):
        parts = [self.address_line_1]
        if self.address_line_2:
            parts.append(self.address_line_2)
        parts.append(f'{self.city} {self.postcode}')
        return ', '.join(parts)

    def as_booking_dict(self):
        return {
            'id': self.pk,
            'label': self.display_label,
            'address_line_1': self.address_line_1,
            'address_line_2': self.address_line_2 or '',
            'city': self.city,
            'postcode': self.postcode,
            'is_default': self.is_default,
            'summary': self.summary,
        }

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.is_default:
            SavedAddress.objects.filter(
                user=self.user,
                is_default=True,
            ).exclude(pk=self.pk).update(is_default=False)


class BusinessProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='business_profile',
    )
    company_name = models.CharField(max_length=200)
    invoice_email = models.EmailField(
        help_text='Where invoices and booking confirmations are sent.',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Business profile'
        verbose_name_plural = 'Business profiles'

    def __str__(self):
        return self.company_name


class Property(models.Model):
    """A rental or managed property for property-partner (business) accounts."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='properties',
    )
    reference = models.CharField(
        max_length=100,
        blank=True,
        help_text='Optional label, e.g. Flat 4, Oak House or tenancy ref.',
    )
    address_line_1 = models.CharField(max_length=255)
    address_line_2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100)
    postcode = models.CharField(max_length=10)
    access_instructions = models.TextField(
        blank=True,
        help_text='Keysafe codes, agent contact, parking — shown to your technician.',
    )
    contact_name = models.CharField(max_length=150, blank=True)
    contact_phone = models.CharField(max_length=20, blank=True)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_default', '-updated_at']
        verbose_name_plural = 'Properties'

    def __str__(self):
        return self.display_label

    @property
    def display_label(self):
        if self.reference:
            return self.reference
        return self.address_line_1

    @property
    def summary(self):
        parts = [self.address_line_1]
        if self.address_line_2:
            parts.append(self.address_line_2)
        parts.append(f'{self.city} {self.postcode}')
        return ', '.join(parts)

    def as_booking_dict(self):
        return {
            'id': self.pk,
            'label': self.display_label,
            'reference': self.reference,
            'address_line_1': self.address_line_1,
            'address_line_2': self.address_line_2 or '',
            'city': self.city,
            'postcode': self.postcode,
            'access_instructions': self.access_instructions,
            'contact_name': self.contact_name,
            'contact_phone': self.contact_phone,
            'is_default': self.is_default,
            'summary': self.summary,
            'is_property': True,
        }

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.is_default:
            Property.objects.filter(
                user=self.user,
                is_default=True,
            ).exclude(pk=self.pk).update(is_default=False)
