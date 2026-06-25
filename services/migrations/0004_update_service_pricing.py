from django.db import migrations


def apply_service_catalog(apps, schema_editor):
    from services.catalog import sync_service_catalog

    sync_service_catalog()


class Migration(migrations.Migration):

    dependencies = [
        ('services', '0003_service_duration_minutes'),
    ]

    operations = [
        migrations.RunPython(apply_service_catalog, migrations.RunPython.noop),
    ]
