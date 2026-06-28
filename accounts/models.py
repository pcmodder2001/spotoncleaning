from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.exceptions import PermissionDenied
from django.db import models
from django.utils import timezone

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
