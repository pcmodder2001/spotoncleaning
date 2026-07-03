from django.contrib import admin

from hr.models import EmployeeProfile, OnboardingTask, Payslip, RotaShift, Vehicle, VehicleAudit, VehicleAuditPhoto


class VehicleAuditPhotoInline(admin.TabularInline):
    model = VehicleAuditPhoto
    extra = 0
    readonly_fields = ('uploaded_at',)


@admin.register(VehicleAudit)
class VehicleAuditAdmin(admin.ModelAdmin):
    list_display = ('vehicle', 'week_start', 'submitted_by', 'mileage', 'submitted_at')
    list_filter = ('week_start',)
    search_fields = ('vehicle__registration', 'submitted_by__email')
    inlines = [VehicleAuditPhotoInline]


class OnboardingTaskInline(admin.TabularInline):
    model = OnboardingTask
    extra = 0


@admin.register(EmployeeProfile)
class EmployeeProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'job_title', 'employment_type', 'start_date', 'is_active')
    search_fields = ('user__email', 'user__first_name', 'user__last_name', 'employee_number')
    inlines = [OnboardingTaskInline]


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ('registration', 'make', 'model', 'assigned_to', 'uses_adblue', 'mot_expiry', 'is_active')
    search_fields = ('registration', 'make', 'model')


@admin.register(RotaShift)
class RotaShiftAdmin(admin.ModelAdmin):
    list_display = ('employee', 'date', 'shift_type', 'start_time', 'end_time')
    list_filter = ('shift_type', 'date')


@admin.register(Payslip)
class PayslipAdmin(admin.ModelAdmin):
    list_display = ('employee', 'period_start', 'period_end', 'net_pay', 'is_published', 'pay_date')
    list_filter = ('is_published',)
