from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0022_promocode_stackable'),
    ]

    operations = [
        migrations.AddField(
            model_name='promocode',
            name='count_addons',
            field=models.BooleanField(
                default=False,
                help_text='When set, add-on services also count toward the minimum appliance total.',
            ),
        ),
        migrations.AlterField(
            model_name='promocode',
            name='min_appliance_count',
            field=models.PositiveIntegerField(
                blank=True,
                help_text='Minimum number of appliances required for auto promos.',
                null=True,
            ),
        ),
    ]
