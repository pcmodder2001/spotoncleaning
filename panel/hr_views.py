from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from accounts.roles import UserRole
from hr.models import (
    EmployeeInvite,
    EmployeeProfile,
    OnboardingTask,
    Payslip,
    RotaShift,
    ShiftType,
    TaskCompletionMode,
    Vehicle,
    VehicleAudit,
    VehicleAuditPhoto,
)
from hr.media_access import can_view_vehicle_audit, vehicle_audit_photo_url
from hr.vehicle_audits import (
    AUDIT_PHOTO_LABELS,
    audit_due_for_user,
    audit_photo_sections,
    audit_photo_steps,
    audit_week_start,
    current_week_audit,
    get_assigned_vehicle,
    required_photo_types,
)
from hr.documents import document_context, get_document_meta
from hr.invites import create_employee_invite, invite_registration_url, send_employee_invite_email
from hr.services import (
    create_default_onboarding,
    ensure_employee_profile,
    hr_is_self_view,
    hr_manage_mode,
    is_hr_staff,
    redirect_if_onboarding_required,
    staff_users_queryset,
)
from panel.decorators import ops_required, sysadmin_required

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


def _onboarding_task_redirect(request, task, next_url=None):
    url = (next_url or request.POST.get('next') or '').strip()
    if not url:
        from django.urls import reverse
        url = reverse('panel:hr_onboarding')
        if request.user.can_manage_site:
            url = f'{url}?employee={task.employee.user_id}'
    base = url.split('#')[0]
    return redirect(f'{base}#onboarding-task-{task.pk}')


def _onboarding_wants_json(request):
    return (
        request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        or 'application/json' in request.headers.get('Accept', '')
    )


def _onboarding_json_error(message, status=400):
    return JsonResponse({'ok': False, 'error': message}, status=status)


def _onboarding_task_row_html(request, task):
    return render_to_string(
        'panel/hr/includes/onboarding_task_row.html',
        {
            'task': task,
            'can_manage': hr_manage_mode(request),
        },
        request=request,
    )


def _onboarding_json_success(request, task, message='Task updated.'):
    profile = task.employee
    return JsonResponse({
        'ok': True,
        'message': message,
        'task_id': task.pk,
        'html': _onboarding_task_row_html(request, task),
        'progress': profile.onboarding_progress,
        'open_tasks': profile.onboarding_tasks.filter(is_completed=False).count(),
    })


@ops_required
def hr_dashboard_view(request):
    denied = _require_hr_staff(request)
    if denied:
        return denied

    onboarding_redirect = redirect_if_onboarding_required(request)
    if onboarding_redirect:
        return onboarding_redirect

    today = timezone.localdate()
    profile = EmployeeProfile.objects.filter(user=request.user).first()

    if hr_manage_mode(request):
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
        audit_week = audit_week_start(today)
        audited_ids = VehicleAudit.objects.filter(week_start=audit_week).values_list('vehicle_id', flat=True)
        missing_vehicle_audits = Vehicle.objects.filter(
            is_active=True,
            assigned_to__isnull=False,
        ).exclude(pk__in=audited_ids).count()
        return render(request, 'panel/hr/dashboard_admin.html', {
            'staff_count': staff.count(),
            'profile_count': profiles.count(),
            'vehicle_count': Vehicle.objects.filter(is_active=True).count(),
            'incomplete_onboarding': incomplete_onboarding,
            'mot_due': mot_due,
            'insurance_due': insurance_due,
            'missing_vehicle_audits': missing_vehicle_audits,
            'audit_week': audit_week,
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

    assigned_vehicle = get_assigned_vehicle(request.user)
    audit_week = audit_week_start(today)
    current_audit = current_week_audit(assigned_vehicle)

    return render(request, 'panel/hr/dashboard_staff.html', {
        'profile': profile,
        'onboarding_progress': profile.onboarding_progress if profile else 0,
        'open_tasks': profile.onboarding_tasks.filter(is_completed=False).count() if profile else 0,
        'my_shifts': my_shifts,
        'week_start': week_start,
        'week_end': week_end,
        'my_payslips': my_payslips,
        'assigned_vehicle': assigned_vehicle,
        'vehicle_audit_due': audit_due_for_user(request.user),
        'current_vehicle_audit': current_audit,
        'vehicle_audit_week': audit_week,
    })


@sysadmin_required
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


@sysadmin_required
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


@ops_required
@require_POST
def hr_onboarding_toggle_view(request, task_pk):
    wants_json = _onboarding_wants_json(request)
    denied = _require_hr_staff(request)
    if denied:
        if wants_json:
            return _onboarding_json_error('HR features are only available to staff accounts.', 403)
        return denied

    task = get_object_or_404(
        OnboardingTask.objects.select_related('employee__user'),
        pk=task_pk,
    )
    if not request.user.can_manage_site and task.employee.user_id != request.user.pk:
        if wants_json:
            return _onboarding_json_error('You can only update your own onboarding tasks.')
        messages.error(request, 'You can only update your own onboarding tasks.')
        return redirect('panel:hr_onboarding')

    completed = request.POST.get('completed') == '1'
    if not task.can_toggle_by(request.user):
        if wants_json:
            return _onboarding_json_error(
                'This task must be completed through the document or form provided.',
            )
        messages.error(request, 'This task must be completed through the document or form provided.')
        return _onboarding_task_redirect(request, task)
    task.mark_complete(completed)
    message = f'"{task.title}" marked complete.' if completed else f'"{task.title}" reopened.'
    if wants_json:
        return _onboarding_json_success(request, task, message)
    messages.success(request, message)
    return _onboarding_task_redirect(request, task)


@ops_required
def hr_onboarding_view(request):
    denied = _require_hr_staff(request)
    if denied:
        return denied

    if hr_manage_mode(request):
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

    if hr_manage_mode(request) and request.method == 'POST':
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
    if hr_manage_mode(request):
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
        'can_manage': hr_manage_mode(request),
        'pending_invites': pending_invites,
        'employment_types': EmployeeProfile._meta.get_field('employment_type').choices,
    })


@sysadmin_required
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


@sysadmin_required
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
        vehicle.uses_adblue = request.POST.get('uses_adblue') == 'on'
        vehicle.notes = request.POST.get('notes', '')
        vehicle.is_active = request.POST.get('is_active') == 'on'
        vehicle.save()
        messages.success(request, f'Vehicle {vehicle.registration} updated.')
        return redirect('panel:hr_vehicle_list')
    return render(request, 'panel/hr/vehicles/edit.html', {
        'vehicle': vehicle,
        'staff': staff_users_queryset(),
    })


@ops_required
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
    if hr_is_self_view(request):
        staff = staff.filter(pk=request.user.pk)

    if hr_manage_mode(request) and request.method == 'POST':
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
        'can_manage': hr_manage_mode(request),
        'staff': staff if hr_manage_mode(request) else None,
    })


@ops_required
def hr_payslip_list_view(request):
    denied = _require_hr_staff(request)
    if denied:
        return denied

    if hr_manage_mode(request):
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
        'can_manage': hr_manage_mode(request),
        'staff': staff_users_queryset() if hr_manage_mode(request) else None,
        'employee_filter': request.GET.get('employee', ''),
    })


@sysadmin_required
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


@ops_required
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


@ops_required
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


@ops_required
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
    return _onboarding_task_redirect(request, task)


@ops_required
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
            return _onboarding_task_redirect(request, task)
        messages.error(request, 'Please provide a contact name and phone number.')

    return render(request, 'panel/hr/onboarding_emergency.html', {
        'task': task,
        'profile': profile,
    })


def _can_view_vehicle_audit(request, audit):
    return can_view_vehicle_audit(request, audit)


def _vehicle_audit_list_url(request):
    from django.urls import reverse
    url = reverse('panel:hr_vehicle_audit_list')
    if hr_is_self_view(request):
        return f'{url}?view=mine'
    return url


def _vehicle_audit_detail_url(request, pk):
    from django.urls import reverse
    url = reverse('panel:hr_vehicle_audit_detail', kwargs={'pk': pk})
    if hr_is_self_view(request):
        return f'{url}?view=mine'
    return url


@ops_required
def hr_vehicle_audit_list_view(request):
    denied = _require_hr_staff(request)
    if denied:
        return denied

    week_start = audit_week_start()
    if hr_manage_mode(request):
        audits = VehicleAudit.objects.select_related('vehicle', 'submitted_by').order_by('-week_start', '-submitted_at')
        vehicle_filter = request.GET.get('vehicle')
        week_filter = request.GET.get('week')
        if vehicle_filter:
            audits = audits.filter(vehicle_id=vehicle_filter)
        if week_filter:
            try:
                audits = audits.filter(week_start=date.fromisoformat(week_filter))
            except ValueError:
                pass
        missing_vehicles = Vehicle.objects.filter(
            is_active=True,
            assigned_to__isnull=False,
        ).exclude(
            pk__in=VehicleAudit.objects.filter(week_start=week_start).values_list('vehicle_id', flat=True),
        ).select_related('assigned_to')
    else:
        vehicle = get_assigned_vehicle(request.user)
        audits = VehicleAudit.objects.filter(
            vehicle=vehicle,
        ).select_related('vehicle', 'submitted_by').order_by('-week_start') if vehicle else VehicleAudit.objects.none()
        missing_vehicles = []
        vehicle_filter = ''
        week_filter = ''

    assigned_vehicle = get_assigned_vehicle(request.user)
    return render(request, 'panel/hr/vehicles/audit_list.html', {
        'audits': audits[:100],
        'can_manage': hr_manage_mode(request),
        'vehicles': Vehicle.objects.filter(is_active=True).order_by('registration') if hr_manage_mode(request) else None,
        'vehicle_filter': request.GET.get('vehicle', ''),
        'week_filter': request.GET.get('week', ''),
        'missing_vehicles': missing_vehicles,
        'audit_week': week_start,
        'assigned_vehicle': assigned_vehicle,
        'vehicle_audit_due': audit_due_for_user(request.user),
        'current_vehicle_audit': current_week_audit(assigned_vehicle),
    })


@ops_required
def hr_vehicle_audit_submit_view(request):
    denied = _require_hr_staff(request)
    if denied:
        return denied

    vehicle = get_assigned_vehicle(request.user)
    if not vehicle:
        messages.error(request, 'No company vehicle is assigned to you.')
        return redirect(_vehicle_audit_list_url(request))

    week_start = audit_week_start()
    existing = current_week_audit(vehicle)
    if existing:
        messages.info(request, 'You have already submitted this week\'s vehicle audit.')
        return redirect(_vehicle_audit_detail_url(request, existing.pk))

    required = required_photo_types(vehicle)
    photo_steps = audit_photo_steps(vehicle)

    if request.method == 'POST':
        mileage_raw = request.POST.get('mileage', '').strip()
        if not mileage_raw.isdigit():
            messages.error(request, 'Enter the current mileage as a whole number.')
        else:
            missing = [photo_type for photo_type in required if photo_type not in request.FILES]
            if missing:
                labels = ', '.join(AUDIT_PHOTO_LABELS[t] for t in missing[:4])
                suffix = '…' if len(missing) > 4 else ''
                messages.error(request, f'Please add all required photos. Still needed: {labels}{suffix}')
            else:
                mileage = int(mileage_raw)
                audit = VehicleAudit.objects.create(
                    vehicle=vehicle,
                    submitted_by=request.user,
                    week_start=week_start,
                    mileage=mileage,
                    notes=request.POST.get('notes', '').strip(),
                )
                for photo_type in required:
                    VehicleAuditPhoto.objects.create(
                        audit=audit,
                        photo_type=photo_type,
                        image=request.FILES[photo_type],
                    )
                vehicle.mileage = mileage
                vehicle.save(update_fields=['mileage', 'updated_at'])
                messages.success(request, f'Weekly vehicle audit submitted for {vehicle.registration}.')
                return redirect(_vehicle_audit_detail_url(request, audit.pk))

    return render(request, 'panel/hr/vehicles/audit_form.html', {
        'vehicle': vehicle,
        'photo_steps': photo_steps,
        'week_start': week_start,
        'required_count': len(required),
    })


@ops_required
def hr_vehicle_audit_detail_view(request, pk):
    denied = _require_hr_staff(request)
    if denied:
        return denied

    audit = get_object_or_404(
        VehicleAudit.objects.select_related('vehicle', 'submitted_by').prefetch_related('photos'),
        pk=pk,
    )
    if not _can_view_vehicle_audit(request, audit):
        raise Http404

    photo_map = {photo.photo_type: photo for photo in audit.photos.all()}
    photo_rows = []
    for photo_type in required_photo_types(audit.vehicle):
        photo = photo_map.get(photo_type)
        photo_rows.append({
            'type': photo_type,
            'label': AUDIT_PHOTO_LABELS[photo_type],
            'photo': photo,
            'photo_url': vehicle_audit_photo_url(request, audit, photo) if photo else '',
        })

    return render(request, 'panel/hr/vehicles/audit_detail.html', {
        'audit': audit,
        'photo_rows': photo_rows,
        'can_manage': hr_manage_mode(request),
    })


@ops_required
@require_GET
def hr_vehicle_audit_photo_view(request, audit_pk, photo_pk):
    import mimetypes

    audit = get_object_or_404(VehicleAudit.objects.select_related('vehicle'), pk=audit_pk)
    photo = get_object_or_404(VehicleAuditPhoto, pk=photo_pk, audit=audit)
    if not can_view_vehicle_audit(request, audit):
        raise Http404
    if not photo.image:
        raise Http404

    content_type, _ = mimetypes.guess_type(photo.image.name)
    response = FileResponse(
        photo.image.open('rb'),
        content_type=content_type or 'image/jpeg',
    )
    response['Cache-Control'] = 'private, max-age=3600'
    return response
