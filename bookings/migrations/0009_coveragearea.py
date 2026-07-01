from decimal import Decimal

from django.db import migrations, models


def seed_coverage_areas(apps, schema_editor):
    CoverageArea = apps.get_model('bookings', 'CoverageArea')
    # Inline seed data — migration 0010 replaces these with town-level areas.
    legacy_areas = [
        {
            'slug': 'leeds',
            'name': 'Leeds',
            'admin_district': 'Leeds',
            'postcode_prefix': 'LS',
            'map_color': '#0e7490',
            'center_lat': '53.8008',
            'center_lng': '-1.5491',
            'boundary': [],
            'sort_order': 10,
        },
        {
            'slug': 'bradford',
            'name': 'Bradford',
            'admin_district': 'Bradford',
            'postcode_prefix': 'BD',
            'map_color': '#0891b2',
            'center_lat': '53.7950',
            'center_lng': '-1.7594',
            'boundary': [],
            'sort_order': 20,
        },
        {
            'slug': 'calderdale',
            'name': 'Calderdale',
            'admin_district': 'Calderdale',
            'postcode_prefix': 'HX',
            'map_color': '#155e75',
            'center_lat': '53.7256',
            'center_lng': '-1.8636',
            'boundary': [],
            'sort_order': 30,
        },
        {
            'slug': 'kirklees',
            'name': 'Kirklees',
            'admin_district': 'Kirklees',
            'postcode_prefix': 'HD',
            'map_color': '#059669',
            'center_lat': '53.6458',
            'center_lng': '-1.7850',
            'boundary': [],
            'sort_order': 40,
        },
        {
            'slug': 'wakefield',
            'name': 'Wakefield',
            'admin_district': 'Wakefield',
            'postcode_prefix': 'WF',
            'map_color': '#0284c7',
            'center_lat': '53.6833',
            'center_lng': '-1.5059',
            'boundary': [],
            'sort_order': 50,
        },
    ]

    for area in legacy_areas:
        CoverageArea.objects.update_or_create(
            slug=area['slug'],
            defaults={
                'name': area['name'],
                'admin_district': area['admin_district'],
                'postcode_prefix': area['postcode_prefix'],
                'enabled': True,
                'map_color': area['map_color'],
                'center_lat': Decimal(area['center_lat']),
                'center_lng': Decimal(area['center_lng']),
                'boundary': area['boundary'],
                'sort_order': area['sort_order'],
            },
        )


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0008_booking_reminder_sent_at'),
    ]

    operations = [
        migrations.CreateModel(
            name='CoverageArea',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('slug', models.SlugField(max_length=40, unique=True)),
                ('name', models.CharField(max_length=100)),
                ('admin_district', models.CharField(help_text='Matches postcodes.io admin_district for validation.', max_length=100, unique=True)),
                ('postcode_prefix', models.CharField(help_text='Postcode area prefix used as a fallback (e.g. LS, WF).', max_length=4)),
                ('enabled', models.BooleanField(default=True)),
                ('map_color', models.CharField(default='#0e7490', max_length=7)),
                ('center_lat', models.DecimalField(decimal_places=6, max_digits=9)),
                ('center_lng', models.DecimalField(decimal_places=6, max_digits=9)),
                ('boundary', models.JSONField(blank=True, default=list, help_text='Polygon coordinates as [[lat, lng], ...] for the admin map.')),
                ('sort_order', models.PositiveSmallIntegerField(default=0)),
            ],
            options={
                'ordering': ['sort_order', 'name'],
            },
        ),
        migrations.RunPython(seed_coverage_areas, migrations.RunPython.noop),
    ]
