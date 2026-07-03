from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from accounts.roles import UserRole
from hr.models import EmployeeInvite, EmployeeProfile, OnboardingTask, Payslip, RotaShift, ShiftType, TaskCompletionMode, Vehicle
from hr.documents import document_context, get_document_meta
from hr.invites import create_employee_invite, invite_registration_url, send_employee_invite_email
from hr.services import (
    create_default_onboarding,
    ensure_employee_profile,
    is_hr_staff,
    redirect_if_onboarding_required,
    staff_users_queryset,
)
from panel.decorators import admin_required, panel_required

User = get_user_model()


def _require_hr_staff(request):
    if not is_hr_staff(request.user):
        messages.error(request, 'HR features are only available to staff accounts.')
        return redirect('panel:dashboard')
    return None


def _week_start(date):
    return date - timedelta(days=date.weekday())


def _parse_decimal(value, default='0'):
    try:
        return Decimal(value or default)
    except InvalidOperation:
        return Decimal(default)


@panel_required
def hr_dashboard_view(request):
    denied = _require_hr_staff(request)
    if denied:
        return denied

    onboarding_redirect = redirect_if_onboarding_required(request)
    if onboarding_redirect:
        return onboarding_redirect

    today = timezone.localdate()
    profile = EmployeeProfile.objects.filter(user=request.user).first()

    if request.user.can_manage_site:
        staff = staff_users_queryset()
        profiles = EmployeeProfile.objects.select_related('user').filter(is_active=True)
        incomplete_onboarding = profiles.filter(
            onboarding_tasks__is_completed=False,
        ).distinct().count()
        mot_due = Vehicle.objects.filter(
            is_active=True,
            mot_expiry__lte=today + timedelta(days=30),
        ).count()
        insurance_due = Vehicle.objects.filter(
            is_active=True,
            insurance_expiry__lte=today + timedelta(days=30),
        ).count()
        return render(request, 'panel/hr/dashboard_admin.html', {
            'staff_count': staff.count(),
            'profile_count': profiles.count(),
            'vehicle_count': Vehicle.objects.filter(is_active=True).count(),
            'incomplete_onboarding': incomplete_onboarding,
            'mot_due': mot_due,
            'insurance_due': insurance_due,
            'recent_payslips': Payslip.objects.select_related('employee').order_by('-pay_date')[:5],
        })

    if not profile:
        profile = ensure_employee_profile(request.user)

    week_start = _week_start(today)
    week_end = week_start + timedelta(days=6)
    my_shifts = RotaShift.objects.filter(
        employee=request.user,
        date__gte=week_start,
        date__lte=week_end,
    ).order_by('date')
    my_payslips = Payslip.objects.filter(
        employee=request.user,
        is_published=True,
    ).order_by('-pay_date')[:5]

    return render(request, 'panel/hr/dashboard_staff.html', {
        'profile': profile,
        'onboarding_progress': profile.onboarding_progress if profile else 0,
        'open_tasks': profile.onboarding_tasks.filter(is_completed=False).count() if profile else 0,
        'my_shifts': my_shifts,
        'week_start': week_start,
        'week_end': week_end,
        'my_payslips': my_payslips,
        'assigned_vehicle': Vehicle.objects.filter(assigned_to=request.user, is_active=True).first(),
    })


@admin_required
def hr_employee_list_view(request):
    staff = staff_users_queryset().select_related('employee_profile')
    query = request.GET.get('q', '').strip()
    if query:
        staff = staff.filter(
            Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
            | Q(email__icontains=query)
            | Q(employee_profile__employee_number__icontains=query)
        )
    return render(request, 'panel/hr/employees/list.html', {
        'staff': staff,
        'query': query,
    })


@admin_required
def hr_employee_edit_view(request, pk):
    user = get_object_or_404(User, pk=pk, role__in=(UserRole.ENGINEER, UserRole.ADMIN))
    profile = ensure_employee_profile(user)

    if request.method == 'POST':
        action = request.POST.get('action', 'save')
        if action == 'reset_onboarding':
            profile.onboarding_tasks.all().delete()
            create_default_onboarding(profile)
            messages.success(request, 'Onboarding checklist reset with default tasks.')
            return redirect('panel:hr_employee_edit', pk=user.pk)

        profile.employee_number = request.POST.get('employee_number', '').strip()
        profile.job_title = request.POST.get('job_title', profile.job_title).strip()
        profile.employment_type = request.POST.get('employment_type', profile.employment_type)
        profile.start_date = request.POST.get('start_date') or None
        profile.end_date = request.POST.get('end_date') or None
        profile.emergency_contact_name = request.POST.get('emergency_contact_name', '').strip()
        profile.emergency_contact_phone = request.POST.get('emergency_contact_phone', '').strip()
        profile.emergency_contact_relationship = request.POST.get('emergency_contact_relationship', '').strip()
        profile.address_line = request.POST.get('address_line', '').strip()
        hourly_raw = request.POST.get('hourly_rate', '').strip()
        profile.hourly_rate = _parse_decimal(hourly_raw) if hourly_raw else None
        profile.notes = request.POST.get('notes', '')
        profile.is_active = request.POST.get('is_active') == 'on'
        profile.save()
        messages.success(request, f'HR profile updated for {user.full_name}.')
        return redirect('panel:hr_employee_list')

    return render(request, 'panel/hr/employees/edit.html', {
        'staff_user': user,
        'profile': profile,
        'employment_types': EmployeeProfile._meta.get_field('employment_type').choices,
    })


@panel_required
@require_POST
def hr_onboarding_toggle_view(request, task_pk):
    denied = _require_hr_staff(request)
    if denied:
        return denied

    task = get_object_or_404(
        OnboardingTask.objects.select_related('employee__user'),
        pk=task_pk,
    )
    if not request.user.can_manage_site and task.employee.user_id != request.user.pk:
        messages.error(request, 'You can only update your own onboarding tasks.')
        return redirect('panel:hr_onboarding')

    completed = request.POST.get('completed') == '1'
    if not task.can_toggle_by(request.user):
        messages.error(request, 'This task must be completed through the document or form provided.')
        return redirect(request.POST.get('next') or 'panel:hr_onboarding')
    task.mark_complete(completed)
    return redirect(request.POST.get('next') or 'panel:hr_onboarding')


@panel_required
def hr_onboarding_view(request):
    denied = _require_hr_staff(request)
    if denied:
        return denied

    if request.user.can_manage_site:
        employee_id = request.GET.get('employee')
        if employee_id:
            user = get_object_or_404(User, pk=employee_id, role__in=(UserRole.ENGINEER, UserRole.ADMIN))
            profile = ensure_employee_profile(user)
        else:
            profile = None
            user = None
        staff = staff_users_queryset()
    else:
        user = request.user
        profile = ensure_employee_profile(user)
        staff = None

    if request.user.can_manage_site and request.method == 'POST':
        action = request.POST.get('action')
        if action == 'send_invite':
            email = request.POST.get('invite_email', '').strip()
            if not email:
                messages.error(request, 'Enter an email address for the invitation.')
            else:
                hourly_raw = request.POST.get('invite_hourly_rate', '').strip()
                invite = create_employee_invite(
                    email=email,
                    invited_by=request.user,
                    first_name=request.POST.get('invite_first_name', '').strip(),
                    last_name=request.POST.get('invite_last_name', '').strip(),
                    job_title=request.POST.get('invite_job_title', 'Cleaning technician').strip(),
                    employment_type=request.POST.get('invite_employment_type', 'full_time'),
                    start_date=request.POST.get('invite_start_date') or None,
                    hourly_rate=_parse_decimal(hourly_raw) if hourly_raw else None,
                    personal_message=request.POST.get('invite_message', '').strip(),
                )
                if send_employee_invite_email(invite):
                    messages.success(request, f'Invitation sent to {email}.')
                else:
                    messages.warning(
                        request,
                        f'Invite created but email could not be sent. Share this link manually: {invite_registration_url(invite)}',
                    )
            employee_id = request.GET.get('employee')
            if employee_id:
                return redirect(f'{request.path}?employee={employee_id}')
            return redirect(request.path)
        if action == 'add_task' and profile:
            OnboardingTask.objects.create(
                employee=profile,
                title=request.POST.get('title', '').strip() or 'New task',
                description=request.POST.get('description', '').strip(),
                category=request.POST.get('category', 'documentation'),
                sort_order=profile.onboarding_tasks.count() * 10 + 10,
            )
            messages.success(request, 'Onboarding task added.')
            return redirect(f'{request.path}?employee={profile.user_id}')

    pending_invites = []
    if request.user.can_manage_site:
        pending_invites = [
            {
                'invite': inv,
                'url': invite_registration_url(inv),
            }
            for inv in EmployeeInvite.objects.filter(accepted_at__isnull=True).order_by('-created_at')[:20]
        ]
    tasks = profile.onboarding_tasks.all() if profile else []
    return render(request, 'panel/hr/onboarding.html', {
        'profile': profile,
        'staff_user': user,
        'staff': staff,
        'tasks': tasks,
        'can_manage': request.user.can_manage_site,
        'pending_invites': pending_invites,
        'employment_types': EmployeeProfile._meta.get_field('employment_type').choices,
    })


@admin_required
def hr_vehicle_list_view(request):
    vehicles = Vehicle.objects.select_related('assigned_to').order_by('registration')
    if request.method == 'POST':
        Vehicle.objects.create(
            registration=request.POST.get('registration', '').strip().upper(),
            make=request.POST.get('make', '').strip(),
            model=request.POST.get('model', '').strip(),
            colour=request.POST.get('colour', '').strip(),
            mot_expiry=request.POST.get('mot_expiry') or None,
            insurance_expiry=request.POST.get('insurance_expiry') or None,
            notes=request.POST.get('notes', '').strip(),
        )
        messages.success(request, 'Vehicle added.')
        return redirect('panel:hr_vehicle_list')
    return render(request, 'panel/hr/vehicles/list.html', {
        'vehicles': vehicles,
        'staff': staff_users_queryset(),
    })


@admin_required
def hr_vehicle_edit_view(request, pk):
    vehicle = get_object_or_404(Vehicle, pk=pk)
    if request.method == 'POST':
        vehicle.registration = request.POST.get('registration', vehicle.registration).strip().upper()
        vehicle.make = request.POST.get('make', vehicle.make).strip()
        vehicle.model = request.POST.get('model', vehicle.model).strip()
        vehicle.colour = request.POST.get('colour', '').strip()
        assigned_id = request.POST.get('assigned_to')
        vehicle.assigned_to_id = int(assigned_id) if assigned_id else None
        vehicle.mot_expiry = request.POST.get('mot_expiry') or None
        vehicle.insurance_expiry = request.POST.get('insurance_expiry') or None
        vehicle.tax_expiry = request.POST.get('tax_expiry') or None
        mileage_raw = request.POST.get('mileage', '').strip()
        vehicle.mileage = int(mileage_raw) if mileage_raw.isdigit() else None
        vehicle.notes = request.POST.get('notes', '')
        vehicle.is_active = request.POST.get('is_active') == 'on'
        vehicle.save()
        messages.success(request, f'Vehicle {vehicle.registration} updated.')
        return redirect('panel:hr_vehicle_list')
    return render(request, 'panel/hr/vehicles/edit.html', {
        'vehicle': vehicle,
        'staff': staff_users_queryset(),
    })


@panel_required
def hr_rota_view(request):
    denied = _require_hr_staff(request)
    if denied:
        return denied

    today = timezone.localdate()
    week_param = request.GET.get('week')
    if week_param:
        try:
            week_start = date.fromisoformat(week_param)
        except ValueError:
            week_start = _week_start(today)
    else:
        week_start = _week_start(today)
    week_start = _week_start(week_start)
    week_end = week_start + timedelta(days=6)
    week_days = [week_start + timedelta(days=i) for i in range(7)]

    staff = staff_users_queryset()
    if not request.user.can_manage_site:
        staff = staff.filter(pk=request.user.pk)

    if request.user.can_manage_site and request.method == 'POST':
        employee_id = request.POST.get('employee')
        shift_date = request.POST.get('date')
        if employee_id and shift_date:
            employee = get_object_or_404(User, pk=employee_id, role__in=(UserRole.ENGINEER, UserRole.ADMIN))
            shift, _created = RotaShift.objects.update_or_create(
                employee=employee,
                date=shift_date,
                defaults={
                    'shift_type': request.POST.get('shift_type', ShiftType.WORK),
                    'start_time': request.POST.get('start_time') or None,
                    'end_time': request.POST.get('end_time') or None,
                    'notes': request.POST.get('notes', '').strip(),
                },
            )
            messages.success(request, f'Rota updated for {employee.full_name} on {shift.date:%d %b}.')
        return redirect(f'{request.path}?week={week_start.isoformat()}')

    shifts = RotaShift.objects.filter(
        date__gte=week_start,
        date__lte=week_end,
        employee__in=staff,
    ).select_related('employee')
    shift_map = {(s.employee_id, s.date): s for s in shifts}

    grid = []
    for member in staff:
        row = {'employee': member, 'days': []}
        for day in week_days:
            row['days'].append(shift_map.get((member.pk, day)))
        grid.append(row)

    prev_week = week_start - timedelta(days=7)
    next_week = week_start + timedelta(days=7)

    return render(request, 'panel/hr/rota.html', {
        'grid': grid,
        'week_days': week_days,
        'week_start': week_start,
        'week_end': week_end,
        'prev_week': prev_week,
        'next_week': next_week,
        'shift_types': ShiftType.choices,
        'can_manage': request.user.can_manage_site,
        'staff': staff if request.user.can_manage_site else None,
    })


@panel_required
def hr_payslip_list_view(request):
    denied = _require_hr_staff(request)
    if denied:
        return denied

    if request.user.can_manage_site:
        payslips = Payslip.objects.select_related('employee').order_by('-pay_date')
        employee_filter = request.GET.get('employee')
        if employee_filter:
            payslips = payslips.filter(employee_id=employee_filter)
    else:
        payslips = Payslip.objects.filter(
            employee=request.user,
            is_published=True,
        ).order_by('-pay_date')

    return render(request, 'panel/hr/payslips/list.html', {
        'payslips': payslips,
        'can_manage': request.user.can_manage_site,
        'staff': staff_users_queryset() if request.user.can_manage_site else None,
        'employee_filter': request.GET.get('employee', ''),
    })


@admin_required
def hr_payslip_create_view(request):
    if request.method == 'POST':
        employee = get_object_or_404(
            User,
            pk=request.POST.get('employee'),
            role__in=(UserRole.ENGINEER, UserRole.ADMIN),
        )
        payslip = Payslip(
            employee=employee,
            period_start=request.POST.get('period_start'),
            period_end=request.POST.get('period_end'),
            pay_date=request.POST.get('pay_date') or timezone.localdate(),
            gross_pay=_parse_decimal(request.POST.get('gross_pay')),
            income_tax=_parse_decimal(request.POST.get('income_tax')),
            national_insurance=_parse_decimal(request.POST.get('national_insurance')),
            pension=_parse_decimal(request.POST.get('pension')),
            other_deductions=_parse_decimal(request.POST.get('other_deductions')),
            reference=request.POST.get('reference', '').strip(),
            notes=request.POST.get('notes', '').strip(),
            is_published=request.POST.get('is_published') == 'on',
        )
        if 'document' in request.FILES:
            payslip.document = request.FILES['document']
        payslip.save()
        messages.success(request, f'Payslip created for {employee.full_name}.')
        return redirect('panel:hr_payslip_list')

    return render(request, 'panel/hr/payslips/form.html', {
        'staff': staff_users_queryset(),
    })


@panel_required
@require_GET
def hr_payslip_download_view(request, pk):
    denied = _require_hr_staff(request)
    if denied:
        return denied

    payslip = get_object_or_404(Payslip, pk=pk)
    if not request.user.can_manage_site:
        if payslip.employee_id != request.user.pk or not payslip.is_published:
            raise Http404
    if not payslip.document:
        messages.error(request, 'No PDF attached to this payslip.')
        return redirect('panel:hr_payslip_list')

    return FileResponse(payslip.document.open('rb'), as_attachment=True, filename=payslip.document.name.split('/')[-1])


def _task_accessible_by(request, task):
    if request.user.can_manage_site:
        return True
    return task.employee.user_id == request.user.pk


@panel_required
def hr_onboarding_document_view(request, task_pk):
    denied = _require_hr_staff(request)
    if denied:
        return denied

    task = get_object_or_404(
        OnboardingTask.objects.select_related('employee__user'),
        pk=task_pk,
    )
    if not _task_accessible_by(request, task):
        messages.error(request, 'You do not have access to that document.')
        return redirect('panel:hr_onboarding')

    meta = get_document_meta(task.document_key)
    if not meta:
        messages.error(request, 'Document not found.')
        return redirect('panel:hr_onboarding')

    ctx = document_context(task.employee)
    ctx.update({
        'task': task,
        'document_title': meta['title'],
        'can_acknowledge': (
            not task.is_completed
            and task.requires_acknowledgment
            and task.completion_mode == TaskCompletionMode.EMPLOYEE
            and task.employee.user_id == request.user.pk
        ),
    })
    return render(request, meta['template'], ctx)


@panel_required
@require_POST
def hr_onboarding_acknowledge_view(request, task_pk):
    denied = _require_hr_staff(request)
    if denied:
        return denied

    task = get_object_or_404(
        OnboardingTask.objects.select_related('employee__user'),
        pk=task_pk,
    )
    if task.employee.user_id != request.user.pk:
        messages.error(request, 'You can only sign your own documents.')
        return redirect('panel:hr_onboarding')
    if task.is_completed:
        return redirect('panel:hr_onboarding')
    if not task.requires_acknowledgment or not task.document_key:
        messages.error(request, 'This task does not require a signature.')
        return redirect('panel:hr_onboarding')

    signed_name = request.POST.get('signed_name', '').strip()
    if not signed_name:
        messages.error(request, 'Enter your full name to sign this document.')
        return redirect('panel:hr_onboarding_document', task_pk=task.pk)
    if signed_name.lower() != request.user.full_name.lower():
        messages.error(request, 'Please enter your full name exactly as shown on your account.')
        return redirect('panel:hr_onboarding_document', task_pk=task.pk)
    if request.POST.get('accept') != 'on':
        messages.error(request, 'You must confirm that you have read and agree to the document.')
        return redirect('panel:hr_onboarding_document', task_pk=task.pk)

    task.mark_acknowledged(signed_name)
    messages.success(request, f'"{task.title}" marked complete.')
    return redirect('panel:hr_onboarding')


@panel_required
def hr_onboarding_emergency_view(request, task_pk):
    denied = _require_hr_staff(request)
    if denied:
        return denied

    task = get_object_or_404(
        OnboardingTask.objects.select_related('employee__user'),
        pk=task_pk,
        form_key='emergency_contact',
    )
    if not _task_accessible_by(request, task):
        messages.error(request, 'You do not have access to that form.')
        return redirect('panel:hr_onboarding')

    profile = task.employee
    if request.method == 'POST' and task.employee.user_id == request.user.pk:
        profile.emergency_contact_name = request.POST.get('emergency_contact_name', '').strip()
        profile.emergency_contact_phone = request.POST.get('emergency_contact_phone', '').strip()
        profile.emergency_contact_relationship = request.POST.get('emergency_contact_relationship', '').strip()
        profile.save(update_fields=[
            'emergency_contact_name',
            'emergency_contact_phone',
            'emergency_contact_relationship',
            'updated_at',
        ])
        if profile.emergency_contact_name and profile.emergency_contact_phone:
            task.mark_complete(True)
            messages.success(request, 'Emergency contact saved.')
            return redirect('panel:hr_onboarding')
        messages.error(request, 'Please provide a contact name and phone number.')

    return render(request, 'panel/hr/onboarding_emergency.html', {
        'task': task,
        'profile': profile,
    })
