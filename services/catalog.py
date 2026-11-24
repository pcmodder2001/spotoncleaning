"""Canonical service catalogue — prices and grouping for booking & website."""

from services.models import Service, ServiceType

ADDITIONAL_ADDON_SORT_ORDER = 20
SAFETY_ADDON_SORT_ORDER = 40

# Created once and then left alone, so a price saved in Admin → Services is not overwritten.
HOMEPAGE_OFFERS = [
    {
        'name': 'The Kitchen Reset',
        'description': (
            'Oven, Hob, Extractor + Splashback\n'
            'Fridge + Freezer\n'
            'Air Fryer\n'
            'Washing Machine\n'
            'Dryer\n'
            'Dishwasher'
        ),
        'price': '0.00',
        'duration_minutes': 180,
        'sort_order': 1,
        'service_type': ServiceType.PACKAGE,
        'exclusive_group': 'home_package',
    },
    {
        'name': 'The Safe Home Package',
        'description': (
            'Everything in The Kitchen Reset\n'
            'PLUS Fire Alarm Check + New Batteries\n'
            'PLUS Carbon Monoxide Alarm Check + New Batteries'
        ),
        'price': '0.00',
        'duration_minutes': 210,
        'sort_order': 2,
        'service_type': ServiceType.PACKAGE,
        'exclusive_group': 'home_package',
    },
    {
        'name': 'Fire alarm installation',
        'description': 'Supply and fit a new fire alarm.',
        'price': '0.00',
        'duration_minutes': 30,
        'sort_order': 41,
        'service_type': ServiceType.ADDON,
        'exclusive_group': '',
    },
    {
        'name': 'Carbon monoxide installation',
        'description': 'Supply and fit a new carbon monoxide alarm.',
        'price': '0.00',
        'duration_minutes': 30,
        'sort_order': 42,
        'service_type': ServiceType.ADDON,
        'exclusive_group': '',
    },
    {
        'name': 'Fridge thermometer installation',
        'description': 'Supply and fit a fridge thermometer.',
        'price': '0.00',
        'duration_minutes': 20,
        'sort_order': 43,
        'service_type': ServiceType.ADDON,
        'exclusive_group': '',
    },
    {
        'name': 'Oven door lock installation',
        'description': 'Supply and fit an oven door lock.',
        'price': '0.00',
        'duration_minutes': 30,
        'sort_order': 44,
        'service_type': ServiceType.ADDON,
        'exclusive_group': '',
    },
    {
        'name': 'Non-slip mat',
        'description': 'Supply and fit a non-slip mat.',
        'price': '0.00',
        'duration_minutes': 20,
        'sort_order': 45,
        'service_type': ServiceType.ADDON,
        'exclusive_group': '',
    },
]

SAFETY_ADDON_ICONS = {
    'Fire alarm installation': 'bi-bell',
    'Carbon monoxide installation': 'bi-cloud',
    'Fridge thermometer installation': 'bi-thermometer-half',
    'Oven door lock installation': 'bi-lock',
    'Non-slip mat': 'bi-grid',
}

SERVICE_CATALOG = [
    {
        'name': 'Single Oven',
        'description': 'Deep clean of a single oven — racks, door glass, and interior surfaces.',
        'price': 50.00,
        'duration_minutes': 60,
        'sort_order': 1,
        'service_type': ServiceType.OVEN,
        'exclusive_group': '',
    },
    {
        'name': 'Double Oven',
        'description': 'Complete cleaning of double ovens including both cavities, racks, and door panels.',
        'price': 60.00,
        'duration_minutes': 75,
        'sort_order': 2,
        'service_type': ServiceType.OVEN,
        'exclusive_group': '',
    },
    {
        'name': 'Freestanding Cooker inc Hob',
        'description': 'Full clean of a freestanding cooker including the oven cavity and hob top.',
        'price': 90.00,
        'duration_minutes': 90,
        'sort_order': 3,
        'service_type': ServiceType.OVEN,
        'exclusive_group': '',
    },
    {
        'name': 'Range Oven inc Hob',
        'description': 'Specialist cleaning for range-style cookers including ovens and hob surfaces.',
        'price': 90.00,
        'duration_minutes': 90,
        'sort_order': 4,
        'service_type': ServiceType.OVEN,
        'exclusive_group': '',
    },
    {
        'name': 'AGA 2 Oven',
        'description': 'Specialist cleaning for a 2-oven AGA — ovens and enamel surfaces restored to shine.',
        'price': 80.00,
        'duration_minutes': 90,
        'sort_order': 5,
        'service_type': ServiceType.OVEN,
        'exclusive_group': '',
    },
    {
        'name': 'AGA 3 Oven',
        'description': 'Specialist cleaning for a 3-oven AGA — all ovens and enamel surfaces.',
        'price': 100.00,
        'duration_minutes': 105,
        'sort_order': 6,
        'service_type': ServiceType.OVEN,
        'exclusive_group': '',
    },
    {
        'name': 'AGA 4 Oven',
        'description': 'Specialist cleaning for a 4-oven AGA — full oven and enamel restoration.',
        'price': 120.00,
        'duration_minutes': 120,
        'sort_order': 7,
        'service_type': ServiceType.OVEN,
        'exclusive_group': '',
    },
    {
        'name': '4 Hob',
        'description': 'Thorough cleaning of a 4-burner hob — grease and burnt-on food removed.',
        'price': 15.00,
        'duration_minutes': 20,
        'sort_order': 11,
        'service_type': ServiceType.ADDON,
        'exclusive_group': 'hob',
    },
    {
        'name': '5 Hob',
        'description': 'Thorough cleaning of a 5-burner hob — grease and burnt-on food removed.',
        'price': 20.00,
        'duration_minutes': 25,
        'sort_order': 12,
        'service_type': ServiceType.ADDON,
        'exclusive_group': 'hob',
    },
    {
        'name': '6-8 Hob',
        'description': 'Thorough cleaning of a 6–8 burner hob — grease and burnt-on food removed.',
        'price': 25.00,
        'duration_minutes': 30,
        'sort_order': 13,
        'service_type': ServiceType.ADDON,
        'exclusive_group': 'hob',
    },
    {
        'name': 'Extractor',
        'description': 'Cleaning of extractor units, filters, and surrounding areas for improved airflow.',
        'price': 25.00,
        'duration_minutes': 25,
        'sort_order': 14,
        'service_type': ServiceType.ADDON,
        'exclusive_group': '',
    },
    {
        'name': 'Standard Microwave',
        'description': 'Interior and exterior deep clean of a standard microwave.',
        'price': 25.00,
        'duration_minutes': 25,
        'sort_order': 21,
        'service_type': ServiceType.ADDON,
        'exclusive_group': '',
    },
    {
        'name': 'Combi Microwave',
        'description': 'Deep clean of a combination microwave oven — interior, exterior, and vents.',
        'price': 45.00,
        'duration_minutes': 35,
        'sort_order': 22,
        'service_type': ServiceType.ADDON,
        'exclusive_group': '',
    },
    {
        'name': 'Standard Fridge',
        'description': 'Full clean of a standard fridge — shelves, drawers, seals, and interior.',
        'price': 60.00,
        'duration_minutes': 45,
        'sort_order': 23,
        'service_type': ServiceType.ADDON,
        'exclusive_group': '',
    },
    {
        'name': 'Standard Fridge Freezer',
        'description': 'Complete clean of a standard fridge freezer — both compartments and all shelving.',
        'price': 75.00,
        'duration_minutes': 60,
        'sort_order': 24,
        'service_type': ServiceType.ADDON,
        'exclusive_group': '',
    },
    {
        'name': 'American Fridge Freezer',
        'description': 'Deep clean of an American-style fridge freezer — interior, exterior, and water dispensers.',
        'price': 90.00,
        'duration_minutes': 75,
        'sort_order': 25,
        'service_type': ServiceType.ADDON,
        'exclusive_group': '',
    },
]

LEGACY_SERVICE_NAMES = [
    'Standard Oven (with Grill)',
    'Aga Cooker',
    'Hob',
    'Extractor Fan',
    'Single Oven Cleaning',
    'Range Cooker Cleaning',
    'Hob Cleaning',
    'Extractor Fan Cleaning',
    'Double Oven Cleaning',
]


def sync_service_catalog():
    for service_data in SERVICE_CATALOG:
        Service.objects.update_or_create(
            name=service_data['name'],
            defaults={**service_data, 'active': True},
        )
    Service.objects.filter(name__in=LEGACY_SERVICE_NAMES).update(active=False)


def split_addon_services(addon_queryset):
    return (
        addon_queryset.filter(sort_order__lt=ADDITIONAL_ADDON_SORT_ORDER),
        addon_queryset.filter(
            sort_order__gte=ADDITIONAL_ADDON_SORT_ORDER,
            sort_order__lt=SAFETY_ADDON_SORT_ORDER,
        ),
        addon_queryset.filter(sort_order__gte=SAFETY_ADDON_SORT_ORDER),
    )


def ensure_homepage_offers():
    """Add homepage packages and safety add-ons if they are missing.

    Existing rows are left unchanged so admin price edits stick.
    """
    for service_data in HOMEPAGE_OFFERS:
        Service.objects.get_or_create(
            name=service_data['name'],
            defaults={**service_data, 'active': True},
        )


def exclusive_group_for(name, service_type):
    lowered = (name or '').lower()
    if lowered.startswith(('4 hob', '5 hob', '6-8 hob', '6–8 hob')):
        return 'hob'
    if service_type == ServiceType.PACKAGE:
        return 'home_package'
    return ''


def booking_services_error(services):
    """Return a validation message, or None when the selection is allowed."""
    hob_services = [service for service in services if service.exclusive_group == 'hob']
    if len(hob_services) > 1:
        return 'Please select only one hob size.'
    packages = [service for service in services if service.service_type == ServiceType.PACKAGE]
    if len(packages) > 1:
        return 'Please select only one home package.'
    if packages and any(service.service_type == ServiceType.OVEN for service in services):
        return (
            'A home package already includes the appliance clean. '
            'Remove individual oven services, or book without a package.'
        )
    return None
