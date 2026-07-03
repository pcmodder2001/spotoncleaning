from datetime import timedelta

from django.utils import timezone

from hr.models import Vehicle, VehicleAudit


AUDIT_PHOTO_LABELS = {
    'mileage_display': 'Odometer / mileage display',
    'fuel_gauge': 'Fuel gauge',
    'adblue_gauge': 'AdBlue gauge',
    'tyre_front_left': 'Front left tyre',
    'tyre_front_right': 'Front right tyre',
    'tyre_rear_left': 'Rear left tyre',
    'tyre_rear_right': 'Rear right tyre',
    'corner_front_left': 'Front left corner (full side view)',
    'corner_front_right': 'Front right corner (full side view)',
    'corner_rear_left': 'Rear left corner (full side view)',
    'corner_rear_right': 'Rear right corner (full side view)',
}

AUDIT_PHOTO_HINTS = {
    'mileage_display': 'Photograph the odometer so the mileage is clearly readable.',
    'fuel_gauge': 'Show the fuel gauge on the dashboard.',
    'adblue_gauge': 'Show the AdBlue level gauge.',
    'tyre_front_left': 'Close-up of the front left tyre and tread.',
    'tyre_front_right': 'Close-up of the front right tyre and tread.',
    'tyre_rear_left': 'Close-up of the rear left tyre and tread.',
    'tyre_rear_right': 'Close-up of the rear right tyre and tread.',
    'corner_front_left': 'Stand at the front left corner — include the full side and any damage.',
    'corner_front_right': 'Stand at the front right corner — include the full side and any damage.',
    'corner_rear_left': 'Stand at the rear left corner — include the full side and any damage.',
    'corner_rear_right': 'Stand at the rear right corner — include the full side and any damage.',
}

BASE_REQUIRED_PHOTO_TYPES = (
    'mileage_display',
    'fuel_gauge',
    'tyre_front_left',
    'tyre_front_right',
    'tyre_rear_left',
    'tyre_rear_right',
    'corner_front_left',
    'corner_front_right',
    'corner_rear_left',
    'corner_rear_right',
)


def audit_week_start(for_date=None):
    day = for_date or timezone.localdate()
    return day - timedelta(days=day.weekday())


def get_assigned_vehicle(user):
    return Vehicle.objects.filter(assigned_to=user, is_active=True).first()


def required_photo_types(vehicle):
    types = list(BASE_REQUIRED_PHOTO_TYPES)
    if vehicle.uses_adblue:
        types.insert(2, 'adblue_gauge')
    return types


def current_week_audit(vehicle):
    if not vehicle:
        return None
    return VehicleAudit.objects.filter(
        vehicle=vehicle,
        week_start=audit_week_start(),
    ).first()


def audit_due_for_user(user):
    vehicle = get_assigned_vehicle(user)
    if not vehicle:
        return False
    return current_week_audit(vehicle) is None


def audit_photo_sections(vehicle):
    sections = [
        {
            'title': 'Dashboard readings',
            'items': [
                {'type': 'mileage_display', 'label': AUDIT_PHOTO_LABELS['mileage_display']},
                {'type': 'fuel_gauge', 'label': AUDIT_PHOTO_LABELS['fuel_gauge']},
            ],
        },
    ]
    if vehicle.uses_adblue:
        sections[0]['items'].append(
            {'type': 'adblue_gauge', 'label': AUDIT_PHOTO_LABELS['adblue_gauge']},
        )
    sections.extend([
        {
            'title': 'Tyres (one photo each)',
            'items': [
                {'type': t, 'label': AUDIT_PHOTO_LABELS[t]}
                for t in (
                    'tyre_front_left',
                    'tyre_front_right',
                    'tyre_rear_left',
                    'tyre_rear_right',
                )
            ],
        },
        {
            'title': 'Vehicle corners (capture each side for damage checks)',
            'items': [
                {'type': t, 'label': AUDIT_PHOTO_LABELS[t]}
                for t in (
                    'corner_front_left',
                    'corner_front_right',
                    'corner_rear_left',
                    'corner_rear_right',
                )
            ],
        },
    ])
    return sections


def audit_photo_steps(vehicle):
    steps = []
    for section in audit_photo_sections(vehicle):
        for item in section['items']:
            steps.append({
                'type': item['type'],
                'label': item['label'],
                'section': section['title'],
                'hint': AUDIT_PHOTO_HINTS.get(item['type'], ''),
            })
    return steps
