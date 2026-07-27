from decimal import Decimal

from django.db import migrations, models


def create_multi_appliance_promo(apps, schema_editor):
    PromoCode = apps.get_model('bookings', 'PromoCode')
    PromoCode.objects.get_or_create(
        code='MULTI10',
        defaults={
            'description': '10% off when you book 2 or more appliances',
            'discount_type': 'percent',
            'discount_value': Decimal('10.00'),
            'auto_apply': True,
            'min_appliance_count': 2,
            'active': True,
        },
    )


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0020_booking_pricing_snapshot'),
    ]

    operations = [
        migrations.AddField(
            model_name='promocode',
            name='auto_apply',
            field=models.BooleanField(
                default=False,
                help_text='Apply automatically when booking conditions are met (no code required).',
            ),
        ),
        migrations.AddField(
            model_name='promocode',
            name='min_appliance_count',
            field=models.PositiveIntegerField(
                blank=True,
                help_text='Minimum number of main appliances (oven-type services) required for auto promos.',
                null=True,
            ),
        ),
        migrations.RunPython(create_multi_appliance_promo, migrations.RunPython.noop),
    ]
