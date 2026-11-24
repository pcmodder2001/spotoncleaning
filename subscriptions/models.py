from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class KitchenSafeSubscription(models.Model):
    """Monthly KITCHENSafe kitchen reset subscription."""

    PLAN_CODE = 'kitchensafe'
    PLAN_NAME = 'KITCHENSafe'
    DEFAULT_MONTHLY_PRICE = Decimal('89.00')

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending payment'
        ACTIVE = 'active', 'Active'
        PAUSED = 'paused', 'Paused'
        CANCELLED = 'cancelled', 'Cancelled'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='kitchen_safe_subscriptions',
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    monthly_price = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=DEFAULT_MONTHLY_PRICE,
    )

    # Person receiving the visits (often an elderly relative)
    contact_name = models.CharField(max_length=200)
    contact_phone = models.CharField(max_length=40)
    contact_email = models.EmailField(blank=True)

    address_line_1 = models.CharField(max_length=255)
    address_line_2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100)
    postcode = models.CharField(max_length=20)

    # Family / carers who receive same-day photo reports (1–3)
    photo_email_1 = models.EmailField()
    photo_email_2 = models.EmailField(blank=True)
    photo_email_3 = models.EmailField(blank=True)

    notes = models.TextField(
        blank=True,
        help_text='Internal notes — access details, preferences, etc.',
    )
    customer_notes = models.TextField(
        blank=True,
        help_text='Notes from the customer at signup.',
    )

    started_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'KITCHENSafe subscription'
        verbose_name_plural = 'KITCHENSafe subscriptions'

    def __str__(self):
        return f'{self.PLAN_NAME} — {self.contact_name} ({self.postcode})'

    @property
    def plan_name(self):
        return self.PLAN_NAME

    @property
    def full_address(self):
        parts = [self.address_line_1]
        if self.address_line_2:
            parts.append(self.address_line_2)
        parts.append(f'{self.city} {self.postcode}'.strip())
        return ', '.join(p for p in parts if p)

    @property
    def photo_emails(self):
        emails = []
        for value in (self.photo_email_1, self.photo_email_2, self.photo_email_3):
            email = (value or '').strip().lower()
            if email and email not in emails:
                emails.append(email)
        return emails

    @property
    def latest_payment(self):
        return self.payments.order_by('-payment_date', '-pk').first()

    @property
    def is_active(self):
        return self.status == self.Status.ACTIVE

    def clean(self):
        if not self.photo_emails:
            raise ValidationError({'photo_email_1': 'Enter at least one email for photo reports.'})

    def mark_active(self, *, save=True):
        self.status = self.Status.ACTIVE
        if not self.started_at:
            self.started_at = timezone.now()
        if save:
            self.save(update_fields=['status', 'started_at', 'updated_at'])


class SubscriptionPayment(models.Model):
    """Recorded bank-transfer (or other) payment against a subscription."""

    class Method(models.TextChoices):
        BANK_TRANSFER = 'bank_transfer', 'Bank transfer'
        CASH = 'cash', 'Cash'
        OTHER = 'other', 'Other'

    subscription = models.ForeignKey(
        KitchenSafeSubscription,
        on_delete=models.CASCADE,
        related_name='payments',
    )
    amount = models.DecimalField(max_digits=8, decimal_places=2)
    payment_date = models.DateField()
    method = models.CharField(
        max_length=20,
        choices=Method.choices,
        default=Method.BANK_TRANSFER,
    )
    notes = models.CharField(max_length=255, blank=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='recorded_subscription_payments',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-payment_date', '-pk']
        verbose_name = 'Subscription payment'
        verbose_name_plural = 'Subscription payments'

    def __str__(self):
        return (
            f'£{self.amount} on {self.payment_date} '
            f'({self.subscription.contact_name})'
        )
