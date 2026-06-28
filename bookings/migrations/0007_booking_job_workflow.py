# Generated manually for job workflow fields

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0006_admin_ops_features'),
        ('services', '0005_allow_multiple_oven_selection'),
    ]

    operations = [
        migrations.AddField(
            model_name='booking',
            name='completed_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='booking',
            name='completion_signature',
            field=models.TextField(blank=True, help_text='Base64 PNG data URL captured on job completion.'),
        ),
        migrations.AddField(
            model_name='booking',
            name='signed_by_name',
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AddField(
            model_name='booking',
            name='started_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='bookingphoto',
            name='service',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='job_photos',
                to='services.service',
            ),
        ),
    ]
