from decimal import Decimal

from django.db import migrations


def add_barnsley_coverage_area(apps, schema_editor):
    CoverageArea = apps.get_model('bookings', 'CoverageArea')
    from bookings.coverage_data import DEFAULT_COVERAGE_AREAS, REGION_SOUTH_YORKSHIRE

    barnsley = next(area for area in DEFAULT_COVERAGE_AREAS if area['slug'] == 'barnsley')
    CoverageArea.objects.update_or_create(
        slug=barnsley['slug'],
        defaults={
            'name': barnsley['name'],
            'region_group': REGION_SOUTH_YORKSHIRE,
            'admin_districts': barnsley['admin_districts'],
            'postcode_districts': barnsley['postcode_districts'],
            'postcode_area': barnsley.get('postcode_area', ''),
            'enabled': barnsley['enabled'],
            'map_color': barnsley['map_color'],
            'center_lat': Decimal(barnsley['center_lat']),
            'center_lng': Decimal(barnsley['center_lng']),
            'map_radius_km': Decimal(barnsley['map_radius_km']),
            'sort_order': barnsley['sort_order'],
        },
    )


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0010_coveragearea_towns'),
    ]

    operations = [
        migrations.RunPython(add_barnsley_coverage_area, migrations.RunPython.noop),
    ]
