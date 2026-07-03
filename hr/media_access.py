"""Authorised access to HR media (production does not expose /media/ publicly)."""

from django.urls import reverse

from hr.services import hr_manage_mode, is_hr_staff


def can_view_vehicle_audit(request, audit) -> bool:
    if not is_hr_staff(getattr(request, 'user', None)):
        return False
    if hr_manage_mode(request):
        return True
    user = request.user
    if audit.submitted_by_id == user.pk:
        return True
    return audit.vehicle.assigned_to_id == user.pk


def vehicle_audit_photo_url(request, audit, photo) -> str:
    if not photo or not request:
        return ''
    path = reverse(
        'panel:hr_vehicle_audit_photo',
        kwargs={'audit_pk': audit.pk, 'photo_pk': photo.pk},
    )
    return request.build_absolute_uri(path)
