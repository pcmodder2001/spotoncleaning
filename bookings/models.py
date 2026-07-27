from datetime import datetime, timedelta
from decimal import Decimal

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
    class ClosureType(models.TextChoices):
        CLOSED = 'closed', 'Closed'
        FULL = 'full', 'Fully booked'

    date = models.DateField(unique=True)
    reason = models.CharField(max_length=200, blank=True)
    closure_type = models.CharField(
        max_length=10,
        choices=ClosureType.choices,
        default=ClosureType.CLOSED,
    )

    class Meta:
        ordering = ['date']

    def __str__(self):
        label = self.get_closure_type_display()
        if self.reason:
            return f'{self.date} — {label} ({self.reason})'
        return f'{self.date} — {label}'


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
    rental_property = models.ForeignKey(
        'accounts.Property',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='bookings',
    )
    notes = models.TextField(blank=True)
    access_instructions = models.TextField(
        blank=True,
        help_text='Gate codes, parking, key location — for the technician.',
    )
    staff_notes = models.TextField(
        blank=True,
        help_text='Internal notes — not shown to the customer.',
    )
    checklist = models.JSONField(default=dict, blank=True)
    promo_code = models.ForeignKey(
        'bookings.PromoCode',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='bookings',
    )
    discount_amount = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=Decimal('0.00'),
    )
    subtotal = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text='Service subtotal at time of booking (snapshot; not affected by catalog price changes).',
    )
    service_line_items = models.JSONField(
        default=list,
        blank=True,
        help_text='Per-service price snapshot: [{service_id, name, price}, ...].',
    )
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    signed_by_name = models.CharField(max_length=200, blank=True)
    completion_signature = models.TextField(
        blank=True,
        help_text='Base64 PNG data URL captured on job completion.',
    )
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    estimated_duration_minutes = models.PositiveIntegerField(null=True, blank=True)
    reminder_sent_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='When the day-before reminder email/SMS was sent.',
    )
    status = models.CharField(
        max_length=20,
        choices=BookingStatus.choices,
        default=BookingStatus.PENDING,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    marketing_attribution = models.JSONField(
        default=dict,
        blank=True,
        help_text='First-touch UTM tags / fbclid when the customer booked.',
    )

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

    def appointment_time_window(self):
        """Start time, estimated end time, and on-site duration in minutes."""
        from bookings.scheduling import get_booking_duration_minutes

        duration = get_booking_duration_minutes(self)
        start_dt = datetime.combine(self.date, self.time_slot.time)
        end_dt = start_dt + timedelta(minutes=duration)
        return {
            'start': self.time_slot.time,
            'end': end_dt.time(),
            'duration_minutes': duration,
        }

    @property
    def appointment_time_window_display(self):
        window = self.appointment_time_window()
        start = window['start'].strftime('%H:%M')
        end = window['end'].strftime('%H:%M')
        return f'{start} – {end}'

    @property
    def customer_access_notes(self):
        """Notes the customer should see before the visit."""
        return (self.notes or '').strip()

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
    def pricing_is_locked(self):
        return self.status in (BookingStatus.COMPLETED, BookingStatus.CANCELLED)

    def service_price_for(self, service):
        """Booked price for a service, or live catalog price if not snapshotted."""
        for item in self.service_line_items or []:
            if item.get('service_id') == service.pk:
                return Decimal(item['price'])
        return service.price

    @property
    def total_price(self):
        if self.service_line_items:
            return sum(Decimal(item['price']) for item in self.service_line_items)
        if self.subtotal:
            return self.subtotal
        return sum(s.price for s in self.get_services())

    @property
    def discounted_total(self):
        return max(Decimal('0.00'), self.total_price - (self.discount_amount or Decimal('0.00')))

    @property
    def has_promo(self):
        return bool(self.promo_code_id and self.discount_amount)

    def sync_pricing_snapshot(self, services=None, *, save=False):
        """Store current service prices on the booking."""
        if self.pricing_is_locked:
            return self.subtotal or Decimal('0.00')

        if services is None:
            services = list(self.get_services())

        items = []
        total = Decimal('0.00')
        for service in services:
            price = Decimal(service.price).quantize(Decimal('0.01'))
            items.append({
                'service_id': service.pk,
                'name': service.name,
                'price': str(price),
            })
            total += price

        self.service_line_items = items
        self.subtotal = total.quantize(Decimal('0.01'))
        if save and self.pk:
            self.save(update_fields=['subtotal', 'service_line_items', 'updated_at'])
        return self.subtotal

    def recalculate_pricing(self, *, save=True):
        """Recompute promo/discount from services and attached promo rules."""
        if self.pricing_is_locked:
            return
        from bookings.promo import refresh_booking_promo

        refresh_booking_promo(self)
        if save and self.pk:
            self.save(update_fields=['promo_code', 'discount_amount', 'updated_at'])

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

    @property
    def is_reschedulable(self):
        if self.status not in (BookingStatus.PENDING, BookingStatus.CONFIRMED):
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

    def has_complete_job_workflow(self):
        services = list(self.get_services())
        if not services:
            return False
        if not self.signed_by_name or not self.completion_signature:
            return False
        for service in services:
            if not self.photos.filter(
                service=service,
                photo_type=BookingPhoto.PhotoType.BEFORE,
            ).exists():
                return False
            if not self.photos.filter(
                service=service,
                photo_type=BookingPhoto.PhotoType.AFTER,
            ).exists():
                return False
        return True

    def job_workflow_errors(self, services=None):
        """Human-readable list of missing items for job completion."""
        if services is None:
            services = list(self.get_services())
        errors = []
        if not services:
            errors.append('At least one service must be booked.')
        if not self.signed_by_name:
            errors.append('Customer name for sign-off is required.')
        if not self.completion_signature:
            errors.append('Customer signature is required.')
        for service in services:
            if not self.photos.filter(
                service=service,
                photo_type=BookingPhoto.PhotoType.BEFORE,
            ).exists():
                errors.append(f'Before photo required for {service.name}.')
            if not self.photos.filter(
                service=service,
                photo_type=BookingPhoto.PhotoType.AFTER,
            ).exists():
                errors.append(f'After photo required for {service.name}.')
        return errors


class CoverageArea(models.Model):
    """Town or region where online bookings are accepted."""

    slug = models.SlugField(max_length=40, unique=True)
    name = models.CharField(max_length=100)
    region_group = models.CharField(
        max_length=50,
        default='West Yorkshire',
        help_text='Group shown on the admin map (e.g. West Yorkshire, York).',
    )
    admin_districts = models.JSONField(
        default=list,
        blank=True,
        help_text='postcodes.io admin_district names when no postcode list is set.',
    )
    postcode_districts = models.JSONField(
        default=list,
        blank=True,
        help_text='Outward codes covered, e.g. HG1, WF8.',
    )
    postcode_area = models.CharField(
        max_length=4,
        blank=True,
        default='',
        help_text='Two-letter postcode area fallback, e.g. LS, WF.',
    )
    enabled = models.BooleanField(default=True)
    map_color = models.CharField(max_length=7, default='#0e7490')
    center_lat = models.DecimalField(max_digits=9, decimal_places=6)
    center_lng = models.DecimalField(max_digits=9, decimal_places=6)
    map_radius_km = models.DecimalField(
        max_digits=4,
        decimal_places=1,
        default=Decimal('5.0'),
        help_text='Circle radius on the admin map.',
    )
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['sort_order', 'name']

    def __str__(self):
        status = 'on' if self.enabled else 'off'
        return f'{self.name} ({status})'

    @property
    def postcode_label(self):
        if self.postcode_districts:
            districts = self.postcode_districts
            if len(districts) <= 4:
                return ', '.join(districts)
            return f'{districts[0]}-{districts[-1]} ({len(districts)} districts)'
        if self.postcode_area:
            return f'{self.postcode_area} postcodes'
        if self.admin_districts:
            return self.admin_districts[0]
        return 'Custom area'


class EditableCoverageBoundary(models.Model):
    """Admin-drawn service boundary polygon on the coverage map."""

    slug = models.SlugField(max_length=40, unique=True)
    name = models.CharField(max_length=100, default='Service area')
    ring = models.JSONField(
        default=list,
        blank=True,
        help_text='Polygon vertices as [[lat, lng], ...].',
    )
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)
    estimated_postcode_count = models.PositiveIntegerField(
        default=0,
        help_text='Rough count of postcodes inside this boundary.',
    )
    district_count = models.PositiveIntegerField(
        default=0,
        help_text='Rough count of postcode districts (outward codes) inside this boundary.',
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'editable coverage boundaries'

    def __str__(self):
        return self.name


class PromoCode(models.Model):
    class DiscountType(models.TextChoices):
        PERCENT = 'percent', 'Percentage off'
        FIXED = 'fixed', 'Fixed amount off'

    code = models.CharField(max_length=40, unique=True)
    description = models.CharField(max_length=200, blank=True)
    discount_type = models.CharField(
        max_length=10,
        choices=DiscountType.choices,
        default=DiscountType.PERCENT,
    )
    discount_value = models.DecimalField(max_digits=8, decimal_places=2)
    active = models.BooleanField(default=True)
    valid_from = models.DateField(null=True, blank=True)
    valid_until = models.DateField(null=True, blank=True)
    max_uses = models.PositiveIntegerField(null=True, blank=True)
    times_used = models.PositiveIntegerField(default=0)
    min_order_amount = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=Decimal('0.00'),
    )
    auto_apply = models.BooleanField(
        default=False,
        help_text='Apply automatically when booking conditions are met (no code required).',
    )
    min_appliance_count = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text='Minimum number of main appliances (oven-type services) required for auto promos.',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.code.upper()

    def save(self, *args, **kwargs):
        self.code = self.code.upper().strip()
        super().save(*args, **kwargs)

    def is_valid_today(self):
        if not self.active:
            return False
        today = timezone.localdate()
        if self.valid_from and today < self.valid_from:
            return False
        if self.valid_until and today > self.valid_until:
            return False
        if self.max_uses is not None and self.times_used >= self.max_uses:
            return False
        return True

    def calculate_discount(self, subtotal):
        subtotal = Decimal(subtotal)
        if subtotal < self.min_order_amount:
            return Decimal('0.00')
        if self.discount_type == self.DiscountType.PERCENT:
            return min(subtotal, (subtotal * self.discount_value / Decimal('100')).quantize(Decimal('0.01')))
        return min(subtotal, self.discount_value)

    def qualifies_for_services(self, services):
        if not self.is_valid_today():
            return False
        if self.min_appliance_count:
            from services.models import ServiceType

            appliance_count = sum(
                1 for service in services if service.service_type == ServiceType.OVEN
            )
            if appliance_count < self.min_appliance_count:
                return False
        return True


class BookingPhoto(models.Model):
    class PhotoType(models.TextChoices):
        BEFORE = 'before', 'Before'
        AFTER = 'after', 'After'

    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='photos')
    service = models.ForeignKey(
        'services.Service',
        on_delete=models.CASCADE,
        related_name='job_photos',
        null=True,
        blank=True,
    )
    image = models.ImageField(upload_to='booking-photos/%Y/%m/')
    photo_type = models.CharField(max_length=10, choices=PhotoType.choices)
    caption = models.CharField(max_length=200, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['uploaded_at']

    def __str__(self):
        return f'{self.get_photo_type_display()} photo for booking #{self.booking_id}'
