from django.db import migrations


def seed_homepage_offers(apps, schema_editor):
    from services.catalog import ensure_homepage_offers

    ensure_homepage_offers()


class Migration(migrations.Migration):

    dependencies = [
        ('services', '0005_allow_multiple_oven_selection'),
    ]

    operations = [
        migrations.RunPython(seed_homepage_offers, migrations.RunPython.noop),
    ]
