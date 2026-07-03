from django.conf import settings
from django.utils import timezone


DOCUMENT_REGISTRY = {
    'employment_contract': {
        'title': 'Employment Contract',
        'template': 'hr/documents/employment_contract.html',
    },
    'staff_handbook': {
        'title': 'Employee Handbook',
        'template': 'hr/documents/staff_handbook.html',
    },
    'right_to_work': {
        'title': 'Right to Work Declaration',
        'template': 'hr/documents/right_to_work.html',
    },
    'dbs_consent': {
        'title': 'DBS Check Consent Form',
        'template': 'hr/documents/dbs_consent.html',
    },
    'gdpr_employee_privacy': {
        'title': 'Employee Privacy Notice',
        'template': 'hr/documents/gdpr_employee_privacy.html',
    },
    'health_safety': {
        'title': 'Health & Safety Policy',
        'template': 'hr/documents/health_safety.html',
    },
    'confidentiality': {
        'title': 'Confidentiality Agreement',
        'template': 'hr/documents/confidentiality.html',
    },
    'uniform_receipt': {
        'title': 'Uniform & Equipment Receipt',
        'template': 'hr/documents/uniform_receipt.html',
    },
}


def get_document_meta(document_key):
    return DOCUMENT_REGISTRY.get(document_key)


def document_context(profile):
    hourly_rate = profile.hourly_rate
    rate_display = f'£{hourly_rate:.2f} per hour' if hourly_rate else 'As agreed in your offer letter'
    return {
        'employer_name': getattr(settings, 'EMPLOYER_LEGAL_NAME', settings.SITE_NAME),
        'employer_address': getattr(settings, 'EMPLOYER_ADDRESS', 'West Yorkshire, United Kingdom'),
        'employer_rep_name': getattr(settings, 'EMPLOYER_REP_NAME', 'Director'),
        'employer_email': settings.SITE_EMAIL,
        'employer_phone': settings.SITE_PHONE,
        'site_name': settings.SITE_NAME,
        'employee_name': profile.user.full_name,
        'employee_email': profile.user.email,
        'employee_phone': profile.user.phone_number,
        'employee_address': profile.address_line,
        'job_title': profile.job_title,
        'employment_type': profile.get_employment_type_display(),
        'start_date': profile.start_date or timezone.localdate(),
        'hourly_rate': hourly_rate,
        'hourly_rate_display': rate_display,
        'today': timezone.localdate(),
        'today_formatted': timezone.localdate().strftime('%d %B %Y'),
    }
