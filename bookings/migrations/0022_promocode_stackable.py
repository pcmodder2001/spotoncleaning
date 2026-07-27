from django.db import migrations, models


def enable_multi10_stackable(apps, schema_editor):
    PromoCode = apps.get_model('bookings', 'PromoCode')
    PromoCode.objects.filter(code='MULTI10').update(stackable=True)


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0021_promocode_auto_apply'),
    ]

    operations = [
        migrations.AddField(
            model_name='promocode',
            name='stackable',
            field=models.BooleanField(
                default=False,
                help_text='Can be used in conjunction with other stackable offers.',
            ),
        ),
        migrations.AddField(
            model_name='booking',
            name='applied_promos',
            field=models.JSONField(
                blank=True,
                default=list,
                help_text='Snapshot of applied promos: [{id, code, discount, auto}, ...].',
            ),
        ),
        migrations.RunPython(enable_multi10_stackable, migrations.RunPython.noop),
    ]
