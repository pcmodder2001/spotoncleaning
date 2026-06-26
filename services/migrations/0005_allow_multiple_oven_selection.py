from django.db import migrations


def clear_oven_exclusive_group(apps, schema_editor):
    Service = apps.get_model('services', 'Service')
    Service.objects.filter(service_type='oven', exclusive_group='oven').update(exclusive_group='')


class Migration(migrations.Migration):

    dependencies = [
        ('services', '0004_update_service_pricing'),
    ]

    operations = [
        migrations.RunPython(clear_oven_exclusive_group, migrations.RunPython.noop),
    ]
