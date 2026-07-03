from django.urls import reverse

from hr.services import hr_is_self_view, hr_manage_mode

HR_MODE_PAIRED_VIEWS = {
    'hr_dashboard',
    'hr_rota',
    'hr_onboarding',
    'hr_onboarding_document',
    'hr_onboarding_emergency',
    'hr_payslip_list',
    'hr_vehicle_audit_list',
    'hr_vehicle_audit_submit',
    'hr_vehicle_audit_detail',
}


def _hr_mode_tab_urls(request):
    team_url = reverse('panel:hr_dashboard')
    my_url = reverse('panel:hr_dashboard') + '?view=mine'

    match = getattr(request, 'resolver_match', None)
    if not match or not match.url_name:
        return team_url, my_url

    name = match.url_name
    if name in ('hr_onboarding_document', 'hr_onboarding_acknowledge', 'hr_onboarding_emergency'):
        name = 'hr_onboarding'
    if name in ('hr_vehicle_audit_submit', 'hr_vehicle_audit_detail'):
        name = 'hr_vehicle_audit_list'

    if name not in HR_MODE_PAIRED_VIEWS:
        return team_url, my_url

    kwargs = match.kwargs or {}
    try:
        team_url = reverse(f'panel:{name}', kwargs=kwargs)
    except Exception:
        return team_url, my_url

    query_parts = []
    if name == 'hr_onboarding' and request.GET.get('employee'):
        query_parts.append(f'employee={request.GET.get("employee")}')
    if request.GET.get('week'):
        query_parts.append(f'week={request.GET.get("week")}')

    if query_parts:
        team_url = f'{team_url}?{"&".join(query_parts)}'

    my_query = ['view=mine']
    if request.GET.get('week'):
        my_query.insert(0, f'week={request.GET.get("week")}')
    my_url = f'{team_url.split("?")[0]}?{"&".join(my_query)}'
    return team_url, my_url


def hr_view_context(request):
    if not getattr(request, 'user', None) or not request.user.is_authenticated:
        return {}
    team_url, my_url = _hr_mode_tab_urls(request)
    return {
        'hr_self_view': hr_is_self_view(request),
        'hr_manage_mode': hr_manage_mode(request),
        'hr_team_tab_url': team_url,
        'hr_my_tab_url': my_url,
    }
