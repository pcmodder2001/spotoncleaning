from datetime import datetime

from django.conf import settings
from django.db import models
from django.utils import timezone


class BookingStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    CONFIRMED = 'confirmed', 'Confirmed'
    IN_PROGRESS = 'in_progress', 'In Progress'
    COMPLETED = 'completed', 'Completed'
    CANCELLED = 'cancelled', 'Cancelled'


class TimeSlot(models.Model):
    time = models.TimeField(unique=True)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ['time']

    def __str__(self):
        return self.time.strftime('%H:%M')


class WeeklySchedule(models.Model):
    DAY_CHOICES = [
        (0, 'Monday'),
        (1, 'Tuesday'),
        (2, 'Wednesday'),
        (3, 'Thursday'),
        (4, 'Friday'),
        (5, 'Saturday'),
        (6, 'Sunday'),
    ]
    day_of_week = models.IntegerField(choices=DAY_CHOICES, unique=True)
    is_available = models.BooleanField(default=True)

    class Meta:
        ordering = ['day_of_week']

    def __str__(self):
        return self.get_day_of_week_display()


class BlockedDate(models.Model):
    date = models.DateField(unique=True)
    reason = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ['date']

    def __str__(self):
        return f'{self.date} - {self.reason or "Blocked"}'


class Availability(models.Model):
    date = models.DateField()
    time_slot = models.ForeignKey(TimeSlot, on_delete=models.CASCADE, related_name='availabilities')
    available = models.BooleanField(default=True)

    class Meta:
        ordering = ['date', 'time_slot__time']
        unique_together = ['date', 'time_slot']
        verbose_name_plural = 'Availabilities'

    def __str__(self):
        status = 'Available' if self.available else 'Unavailable'
        return f'{self.date} {self.time_slot} - {status}'


class Booking(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='bookings',
        null=True,
        blank=True,
    )
    guest_email = models.EmailField(blank=True)
    guest_first_name = models.CharField(max_length=150, blank=True)
    guest_last_name = models.CharField(max_length=150, blank=True)
    guest_phone = models.CharField(max_length=20, blank=True)
    service = models.ForeignKey(
        'services.Service',
        on_delete=models.PROTECT,
        related_name='legacy_bookings',
        null=True,
        blank=True,
    )
    services = models.ManyToManyField('services.Service', related_name='bookings', blank=True)
    date = models.DateField()
    time_slot = models.ForeignKey(TimeSlot, on_delete=models.PROTECT, related_name='bookings')
    address_line_1 = models.CharField(max_length=255)
    address_line_2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100)
    postcode = models.CharField(max_length=20)
    notes = models.TextField(blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    estimated_duration_minutes = models.PositiveIntegerField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=BookingStatus.choices,
        default=BookingStatus.PENDING,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', '-time_slot__time']

    def __str__(self):
        return f'Booking #{self.pk} - {self.contact_email} - {self.date}'

    @property
    def is_guest(self):
        return self.user_id is None

    @property
    def contact_email(self):
        if self.user_id:
            return self.user.email
        return self.guest_email

    @property
    def contact_first_name(self):
        if self.user_id:
            return self.user.first_name
        return self.guest_first_name

    @property
    def contact_last_name(self):
        if self.user_id:
            return self.user.last_name
        return self.guest_last_name

    @property
    def contact_full_name(self):
        return f'{self.contact_first_name} {self.contact_last_name}'.strip()

    @property
    def contact_phone(self):
        if self.user_id:
            return self.user.phone_number
        return self.guest_phone

    def clear_guest_fields(self):
        self.guest_email = ''
        self.guest_first_name = ''
        self.guest_last_name = ''
        self.guest_phone = ''

    def full_address(self):
        parts = [self.address_line_1]
        if self.address_line_2:
            parts.append(self.address_line_2)
        parts.extend([self.city, self.postcode])
        return ', '.join(parts)

    def get_services(self):
        selected = self.services.all()
        if selected.exists():
            return selected
        if self.service_id:
            from services.models import Service
            return Service.objects.filter(pk=self.service_id)
        return Service.objects.none()

    @property
    def service_summary(self):
        names = list(self.get_services().values_list('name', flat=True))
        return ', '.join(names) if names else '—'

    @property
    def total_price(self):
        return sum(s.price for s in self.get_services())

    @property
    def is_cancellable(self):
        if self.status in (
            BookingStatus.CANCELLED,
            BookingStatus.COMPLETED,
            BookingStatus.IN_PROGRESS,
        ):
            return False
        appointment = timezone.make_aware(
            datetime.combine(self.date, self.time_slot.time)
        )
        return appointment > timezone.now()

    def geocode_and_set_duration(self, service_ids=None):
        from bookings.routing import coords_for_address
        from bookings.scheduling import get_service_duration_minutes

        if self.postcode:
            coords = coords_for_address(self.postcode, self.city, self.address_line_1)
            if coords:
                self.latitude, self.longitude = coords

        if service_ids is None and self.pk:
            service_ids = list(self.get_services().values_list('pk', flat=True))
        if service_ids:
            self.estimated_duration_minutes = get_service_duration_minutes(service_ids)

        self.save(update_fields=[
            'latitude', 'longitude', 'estimated_duration_minutes', 'updated_at',
        ])
