from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0016_booking_rental_property'),
    ]

    operations = [
        migrations.CreateModel(
            name='EditableCoverageBoundary',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('slug', models.SlugField(default='primary', max_length=40, unique=True)),
                ('name', models.CharField(default='Service boundary', max_length=100)),
                ('ring', models.JSONField(blank=True, default=list, help_text='Polygon vertices as [[lat, lng], ...].')),
                ('is_active', models.BooleanField(default=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name_plural': 'editable coverage boundaries',
            },
        ),
    ]
