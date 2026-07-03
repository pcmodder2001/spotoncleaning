from decimal import Decimal
import secrets

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from accounts.roles import UserRole


def payslip_upload_path(instance, filename):
    return f'hr/payslips/{instance.employee_id}/{instance.pay_date:%Y-%m}/{filename}'


class EmploymentType(models.TextChoices):
    FULL_TIME = 'full_time', 'Full time'
    PART_TIME = 'part_time', 'Part time'
    CONTRACTOR = 'contractor', 'Contractor'


class EmployeeProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='employee_profile',
    )
    employee_number = models.CharField(max_length=20, blank=True)
    job_title = models.CharField(max_length=100, default='Cleaning technician')
    employment_type = models.CharField(
        max_length=20,
        choices=EmploymentType.choices,
        default=EmploymentType.FULL_TIME,
    )
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    emergency_contact_name = models.CharField(max_length=150, blank=True)
    emergency_contact_phone = models.CharField(max_length=20, blank=True)
    emergency_contact_relationship = models.CharField(max_length=80, blank=True)
    address_line = models.CharField(max_length=255, blank=True)
    hourly_rate = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Hourly rate for contract documents (optional).',
    )
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['user__first_name', 'user__last_name']

    def __str__(self):
        return self.user.full_name

    def clean(self):
        if self.user_id and self.user.role not in (UserRole.ENGINEER, UserRole.ADMIN):
            raise ValidationError('HR profiles can only be linked to engineer or admin accounts.')

    @property
    def onboarding_progress(self):
        tasks = self.onboarding_tasks.all()
        if not tasks:
            return 100
        completed = tasks.filter(is_completed=True).count()
        return int(completed / tasks.count() * 100)


class OnboardingCategory(models.TextChoices):
    DOCUMENTATION = 'documentation', 'Documentation'
    TRAINING = 'training', 'Training'
    EQUIPMENT = 'equipment', 'Equipment'
    COMPLIANCE = 'compliance', 'Compliance'


class TaskCompletionMode(models.TextChoices):
    EMPLOYEE = 'employee', 'Employee'
    ADMIN = 'admin', 'Manager'


class OnboardingTask(models.Model):
    employee = models.ForeignKey(
        EmployeeProfile,
        on_delete=models.CASCADE,
        related_name='onboarding_tasks',
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    category = models.CharField(
        max_length=20,
        choices=OnboardingCategory.choices,
        default=OnboardingCategory.DOCUMENTATION,
    )
    due_date = models.DateField(null=True, blank=True)
    document_key = models.CharField(max_length=50, blank=True)
    form_key = models.CharField(max_length=50, blank=True)
    requires_acknowledgment = models.BooleanField(default=False)
    completion_mode = models.CharField(
        max_length=20,
        choices=TaskCompletionMode.choices,
        default=TaskCompletionMode.EMPLOYEE,
    )
    acknowledged_name = models.CharField(max_length=150, blank=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    is_completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['sort_order', 'pk']

    def __str__(self):
        return f'{self.employee} — {self.title}'

    @property
    def needs_employee_action(self):
        if self.is_completed or self.completion_mode != TaskCompletionMode.EMPLOYEE:
            return False
        return bool(self.document_key or self.form_key)

    def can_toggle_by(self, user):
        if not user.is_authenticated:
            return False
        if user.can_manage_site:
            return True
        if self.employee.user_id != user.pk:
            return False
        if self.completion_mode == TaskCompletionMode.ADMIN:
            return False
        if self.document_key and self.requires_acknowledgment:
            return False
        if self.form_key:
            return False
        return True

    def mark_complete(self, completed=True):
        self.is_completed = completed
        self.completed_at = timezone.now() if completed else None
        if not completed:
            self.acknowledged_name = ''
            self.acknowledged_at = None
        self.save(update_fields=[
            'is_completed',
            'completed_at',
            'acknowledged_name',
            'acknowledged_at',
        ])

    def mark_acknowledged(self, name):
        self.acknowledged_name = name.strip()
        self.acknowledged_at = timezone.now()
        self.is_completed = True
        self.completed_at = self.acknowledged_at
        self.save(update_fields=[
            'acknowledged_name',
            'acknowledged_at',
            'is_completed',
            'completed_at',
        ])


def employee_invite_token():
    return secrets.token_urlsafe(32)


class EmployeeInvite(models.Model):
    email = models.EmailField()
    token = models.CharField(max_length=64, unique=True, default=employee_invite_token, db_index=True)
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    job_title = models.CharField(max_length=100, default='Cleaning technician')
    employment_type = models.CharField(
        max_length=20,
        choices=EmploymentType.choices,
        default=EmploymentType.FULL_TIME,
    )
    start_date = models.DateField(null=True, blank=True)
    hourly_rate = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    personal_message = models.TextField(blank=True)
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='employee_invites_sent',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='employee_invite',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Invite: {self.email}'

    @property
    def is_valid(self):
        if self.accepted_at:
            return False
        return timezone.now() < self.expires_at

    @property
    def full_name(self):
        return f'{self.first_name} {self.last_name}'.strip() or self.email


class Vehicle(models.Model):
    registration = models.CharField(max_length=12, unique=True)
    make = models.CharField(max_length=80)
    model = models.CharField(max_length=80)
    colour = models.CharField(max_length=40, blank=True)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_vehicles',
    )
    mot_expiry = models.DateField(null=True, blank=True)
    insurance_expiry = models.DateField(null=True, blank=True)
    tax_expiry = models.DateField(null=True, blank=True)
    mileage = models.PositiveIntegerField(null=True, blank=True)
    uses_adblue = models.BooleanField(
        default=False,
        help_text='Driver must photograph AdBlue level in weekly vehicle audits.',
    )
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['registration']

    def __str__(self):
        return f'{self.registration} ({self.make} {self.model})'


def vehicle_audit_photo_path(instance, filename):
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else 'jpg'
    return (
        f'hr/vehicle-audits/{instance.audit.vehicle_id}/'
        f'{instance.audit.week_start:%Y-%m-%d}/{instance.photo_type}.{ext}'
    )


class VehicleAuditPhotoType(models.TextChoices):
    MILEAGE = 'mileage_display', 'Odometer / mileage'
    FUEL = 'fuel_gauge', 'Fuel gauge'
    ADBLUE = 'adblue_gauge', 'AdBlue gauge'
    TYRE_FL = 'tyre_front_left', 'Front left tyre'
    TYRE_FR = 'tyre_front_right', 'Front right tyre'
    TYRE_RL = 'tyre_rear_left', 'Rear left tyre'
    TYRE_RR = 'tyre_rear_right', 'Rear right tyre'
    CORNER_FL = 'corner_front_left', 'Front left corner'
    CORNER_FR = 'corner_front_right', 'Front right corner'
    CORNER_RL = 'corner_rear_left', 'Rear left corner'
    CORNER_RR = 'corner_rear_right', 'Rear right corner'


class VehicleAudit(models.Model):
    vehicle = models.ForeignKey(
        Vehicle,
        on_delete=models.CASCADE,
        related_name='audits',
    )
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='vehicle_audits',
    )
    week_start = models.DateField(
        help_text='Monday of the audit week.',
    )
    mileage = models.PositiveIntegerField()
    notes = models.TextField(blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-week_start', '-submitted_at']
        constraints = [
            models.UniqueConstraint(
                fields=['vehicle', 'week_start'],
                name='unique_vehicle_audit_per_week',
            ),
        ]

    def __str__(self):
        return f'{self.vehicle.registration} — w/c {self.week_start:%d %b %Y}'

    @property
    def week_end(self):
        from datetime import timedelta
        return self.week_start + timedelta(days=6)


class VehicleAuditPhoto(models.Model):
    audit = models.ForeignKey(
        VehicleAudit,
        on_delete=models.CASCADE,
        related_name='photos',
    )
    photo_type = models.CharField(max_length=30, choices=VehicleAuditPhotoType.choices)
    image = models.ImageField(upload_to=vehicle_audit_photo_path)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['photo_type']
        constraints = [
            models.UniqueConstraint(
                fields=['audit', 'photo_type'],
                name='unique_audit_photo_type',
            ),
        ]

    def __str__(self):
        return f'{self.audit} — {self.get_photo_type_display()}'


class ShiftType(models.TextChoices):
    WORK = 'work', 'Working'
    HOLIDAY = 'holiday', 'Holiday'
    SICK = 'sick', 'Sick leave'
    OFF = 'off', 'Day off'
    TRAINING = 'training', 'Training'


class RotaShift(models.Model):
    employee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='rota_shifts',
    )
    date = models.DateField()
    shift_type = models.CharField(
        max_length=20,
        choices=ShiftType.choices,
        default=ShiftType.WORK,
    )
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    notes = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['date', 'start_time']
        constraints = [
            models.UniqueConstraint(
                fields=['employee', 'date'],
                name='unique_rota_shift_per_day',
            ),
        ]

    def __str__(self):
        return f'{self.employee.full_name} — {self.date} ({self.get_shift_type_display()})'


class Payslip(models.Model):
    employee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='payslips',
    )
    period_start = models.DateField()
    period_end = models.DateField()
    pay_date = models.DateField(default=timezone.localdate)
    gross_pay = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    income_tax = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    national_insurance = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    pension = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    other_deductions = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    net_pay = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    reference = models.CharField(max_length=50, blank=True)
    document = models.FileField(upload_to=payslip_upload_path, blank=True)
    is_published = models.BooleanField(
        default=False,
        help_text='Published payslips are visible to the employee.',
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-pay_date', '-pk']

    def __str__(self):
        return f'Payslip {self.employee.full_name} — {self.period_start:%b %Y}'

    def recalculate_net(self):
        deductions = (
            self.income_tax
            + self.national_insurance
            + self.pension
            + self.other_deductions
        )
        self.net_pay = self.gross_pay - deductions

    def save(self, *args, **kwargs):
        self.recalculate_net()
        super().save(*args, **kwargs)
