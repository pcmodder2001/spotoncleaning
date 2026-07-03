from django.contrib.auth import get_user_model

from accounts.roles import UserRole
from hr.models import EmployeeProfile, OnboardingCategory, OnboardingTask, TaskCompletionMode

User = get_user_model()

DEFAULT_ONBOARDING_TASKS = [
    {
        'title': 'Employment contract',
        'description': 'Read and sign your employment contract.',
        'category': OnboardingCategory.DOCUMENTATION,
        'document_key': 'employment_contract',
        'requires_acknowledgment': True,
        'completion_mode': TaskCompletionMode.EMPLOYEE,
    },
    {
        'title': 'Employee handbook',
        'description': 'Read and confirm you understand the staff handbook.',
        'category': OnboardingCategory.DOCUMENTATION,
        'document_key': 'staff_handbook',
        'requires_acknowledgment': True,
        'completion_mode': TaskCompletionMode.EMPLOYEE,
    },
    {
        'title': 'Right to work declaration',
        'description': 'Confirm your right to work in the UK.',
        'category': OnboardingCategory.COMPLIANCE,
        'document_key': 'right_to_work',
        'requires_acknowledgment': True,
        'completion_mode': TaskCompletionMode.EMPLOYEE,
    },
    {
        'title': 'DBS check consent',
        'description': 'Consent to a DBS check where required for your role.',
        'category': OnboardingCategory.COMPLIANCE,
        'document_key': 'dbs_consent',
        'requires_acknowledgment': True,
        'completion_mode': TaskCompletionMode.EMPLOYEE,
    },
    {
        'title': 'Employee privacy notice',
        'description': 'Read how we process your personal data.',
        'category': OnboardingCategory.COMPLIANCE,
        'document_key': 'gdpr_employee_privacy',
        'requires_acknowledgment': True,
        'completion_mode': TaskCompletionMode.EMPLOYEE,
    },
    {
        'title': 'Health & safety policy',
        'description': 'Read and confirm the health & safety policy.',
        'category': OnboardingCategory.TRAINING,
        'document_key': 'health_safety',
        'requires_acknowledgment': True,
        'completion_mode': TaskCompletionMode.EMPLOYEE,
    },
    {
        'title': 'Confidentiality agreement',
        'description': 'Agree to keep customer and business information confidential.',
        'category': OnboardingCategory.COMPLIANCE,
        'document_key': 'confidentiality',
        'requires_acknowledgment': True,
        'completion_mode': TaskCompletionMode.EMPLOYEE,
    },
    {
        'title': 'Emergency contact details',
        'description': 'Provide next-of-kin contact details.',
        'category': OnboardingCategory.DOCUMENTATION,
        'form_key': 'emergency_contact',
        'completion_mode': TaskCompletionMode.EMPLOYEE,
    },
    {
        'title': 'Uniform & equipment receipt',
        'description': 'Sign to confirm uniform and equipment received.',
        'category': OnboardingCategory.EQUIPMENT,
        'document_key': 'uniform_receipt',
        'requires_acknowledgment': True,
        'completion_mode': TaskCompletionMode.EMPLOYEE,
    },
    {
        'title': 'DBS check completed',
        'description': 'Manager confirms disclosure certificate received.',
        'category': OnboardingCategory.COMPLIANCE,
        'completion_mode': TaskCompletionMode.ADMIN,
    },
    {
        'title': 'Vehicle / transport confirmed',
        'description': 'Company vehicle assigned or own transport agreed.',
        'category': OnboardingCategory.EQUIPMENT,
        'completion_mode': TaskCompletionMode.ADMIN,
    },
    {
        'title': 'Health & safety briefing',
        'description': 'In-person H&S walkthrough completed.',
        'category': OnboardingCategory.TRAINING,
        'completion_mode': TaskCompletionMode.ADMIN,
    },
    {
        'title': 'Product & equipment training',
        'description': 'Cleaning products, tools and job workflow training.',
        'category': OnboardingCategory.TRAINING,
        'completion_mode': TaskCompletionMode.ADMIN,
    },
    {
        'title': 'System login & app walkthrough',
        'description': 'Panel access, schedule and job completion demo.',
        'category': OnboardingCategory.TRAINING,
        'completion_mode': TaskCompletionMode.ADMIN,
    },
]


def staff_users_queryset():
    return User.objects.filter(role__in=(UserRole.ENGINEER, UserRole.ADMIN)).order_by(
        'first_name', 'last_name',
    )


def is_hr_staff(user):
    return user.is_authenticated and user.role in (UserRole.ENGINEER, UserRole.ADMIN)


def create_default_onboarding(profile):
    if profile.onboarding_tasks.exists():
        return
    OnboardingTask.objects.bulk_create([
        OnboardingTask(
            employee=profile,
            title=task['title'],
            description=task.get('description', ''),
            category=task.get('category', OnboardingCategory.DOCUMENTATION),
            document_key=task.get('document_key', ''),
            form_key=task.get('form_key', ''),
            requires_acknowledgment=task.get('requires_acknowledgment', False),
            completion_mode=task.get('completion_mode', TaskCompletionMode.EMPLOYEE),
            sort_order=index * 10,
        )
        for index, task in enumerate(DEFAULT_ONBOARDING_TASKS)
    ])


def ensure_employee_profile(user):
    if user.role not in (UserRole.ENGINEER, UserRole.ADMIN):
        return None
    profile, created = EmployeeProfile.objects.get_or_create(
        user=user,
        defaults={'job_title': 'Cleaning technician' if user.role == UserRole.ENGINEER else 'Administration'},
    )
    if created:
        create_default_onboarding(profile)
    return profile


def onboarding_incomplete(user):
    if not user.is_authenticated or user.can_manage_site:
        return False
    profile = EmployeeProfile.objects.filter(user=user).first()
    if not profile:
        return False
    return profile.onboarding_progress < 100


ONBOARDING_EXEMPT_URL_NAMES = {
    'hr_onboarding',
    'hr_onboarding_document',
    'hr_onboarding_acknowledge',
    'hr_onboarding_emergency',
    'logout',
}


def redirect_if_onboarding_required(request):
    from django.shortcuts import redirect
    from django.contrib import messages

    if not onboarding_incomplete(request.user):
        return None
    url_name = getattr(getattr(request, 'resolver_match', None), 'url_name', None)
    if url_name in ONBOARDING_EXEMPT_URL_NAMES:
        return None
    messages.info(
        request,
        'Please complete your onboarding checklist before continuing.',
    )
    return redirect('panel:hr_onboarding')
