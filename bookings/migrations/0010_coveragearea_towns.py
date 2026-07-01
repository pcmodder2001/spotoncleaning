from decimal import Decimal

from django.db import migrations, models


def reseed_town_coverage_areas(apps, schema_editor):
    CoverageArea = apps.get_model('bookings', 'CoverageArea')
    from bookings.coverage_data import DEFAULT_COVERAGE_AREAS

    CoverageArea.objects.all().delete()
    for area in DEFAULT_COVERAGE_AREAS:
        CoverageArea.objects.create(
            slug=area['slug'],
            name=area['name'],
            region_group=area['region_group'],
            admin_districts=area['admin_districts'],
            postcode_districts=area['postcode_districts'],
            postcode_area=area.get('postcode_area', ''),
            enabled=area['enabled'],
            map_color=area['map_color'],
            center_lat=Decimal(area['center_lat']),
            center_lng=Decimal(area['center_lng']),
            map_radius_km=Decimal(area['map_radius_km']),
            sort_order=area['sort_order'],
        )


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0009_coveragearea'),
    ]

    operations = [
        migrations.AddField(
            model_name='coveragearea',
            name='admin_districts',
            field=models.JSONField(blank=True, default=list, help_text='postcodes.io admin_district names when no postcode list is set.'),
        ),
        migrations.AddField(
            model_name='coveragearea',
            name='map_radius_km',
            field=models.DecimalField(decimal_places=1, default=Decimal('5.0'), help_text='Circle radius on the admin map.', max_digits=4),
        ),
        migrations.AddField(
            model_name='coveragearea',
            name='postcode_area',
            field=models.CharField(blank=True, default='', help_text='Two-letter postcode area fallback, e.g. LS, WF.', max_length=4),
        ),
        migrations.AddField(
            model_name='coveragearea',
            name='postcode_districts',
            field=models.JSONField(blank=True, default=list, help_text='Outward codes covered, e.g. HG1, WF8.'),
        ),
        migrations.AddField(
            model_name='coveragearea',
            name='region_group',
            field=models.CharField(default='West Yorkshire', help_text='Group shown on the admin map (e.g. West Yorkshire, York).', max_length=50),
        ),
        migrations.RemoveField(
            model_name='coveragearea',
            name='admin_district',
        ),
        migrations.RemoveField(
            model_name='coveragearea',
            name='boundary',
        ),
        migrations.RemoveField(
            model_name='coveragearea',
            name='postcode_prefix',
        ),
        migrations.RunPython(reseed_town_coverage_areas, migrations.RunPython.noop),
    ]
