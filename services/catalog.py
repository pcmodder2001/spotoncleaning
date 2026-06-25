"""Canonical service catalogue — prices and grouping for booking & website."""

from services.models import Service, ServiceType

ADDITIONAL_ADDON_SORT_ORDER = 20

SERVICE_CATALOG = [
    {
        'name': 'Single Oven',
        'description': 'Deep clean of a single oven — racks, door glass, and interior surfaces.',
        'price': 50.00,
        'duration_minutes': 60,
        'sort_order': 1,
        'service_type': ServiceType.OVEN,
        'exclusive_group': 'oven',
    },
    {
        'name': 'Double Oven',
        'description': 'Complete cleaning of double ovens including both cavities, racks, and door panels.',
        'price': 60.00,
        'duration_minutes': 75,
        'sort_order': 2,
        'service_type': ServiceType.OVEN,
        'exclusive_group': 'oven',
    },
    {
        'name': 'Freestanding Cooker inc Hob',
        'description': 'Full clean of a freestanding cooker including the oven cavity and hob top.',
        'price': 90.00,
        'duration_minutes': 90,
        'sort_order': 3,
        'service_type': ServiceType.OVEN,
        'exclusive_group': 'oven',
    },
    {
        'name': 'Range Oven inc Hob',
        'description': 'Specialist cleaning for range-style cookers including ovens and hob surfaces.',
        'price': 90.00,
        'duration_minutes': 90,
        'sort_order': 4,
        'service_type': ServiceType.OVEN,
        'exclusive_group': 'oven',
    },
    {
        'name': 'AGA 2 Oven',
        'description': 'Specialist cleaning for a 2-oven AGA — ovens and enamel surfaces restored to shine.',
        'price': 80.00,
        'duration_minutes': 90,
        'sort_order': 5,
        'service_type': ServiceType.OVEN,
        'exclusive_group': 'oven',
    },
    {
        'name': 'AGA 3 Oven',
        'description': 'Specialist cleaning for a 3-oven AGA — all ovens and enamel surfaces.',
        'price': 100.00,
        'duration_minutes': 105,
        'sort_order': 6,
        'service_type': ServiceType.OVEN,
        'exclusive_group': 'oven',
    },
    {
        'name': 'AGA 4 Oven',
        'description': 'Specialist cleaning for a 4-oven AGA — full oven and enamel restoration.',
        'price': 120.00,
        'duration_minutes': 120,
        'sort_order': 7,
        'service_type': ServiceType.OVEN,
        'exclusive_group': 'oven',
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
        addon_queryset.filter(sort_order__gte=ADDITIONAL_ADDON_SORT_ORDER),
    )
