from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0018_editablecoverageboundary_sort_order'),
    ]

    operations = [
        migrations.AddField(
            model_name='editablecoverageboundary',
            name='district_count',
            field=models.PositiveIntegerField(
                default=0,
                help_text='Rough count of postcode districts (outward codes) inside this boundary.',
            ),
        ),
        migrations.AddField(
            model_name='editablecoverageboundary',
            name='estimated_postcode_count',
            field=models.PositiveIntegerField(
                default=0,
                help_text='Rough count of postcodes inside this boundary.',
            ),
        ),
    ]
