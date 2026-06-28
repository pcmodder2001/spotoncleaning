from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0007_booking_job_workflow'),
    ]

    operations = [
        migrations.AddField(
            model_name='booking',
            name='reminder_sent_at',
            field=models.DateTimeField(
                blank=True,
                help_text='When the day-before reminder email/SMS was sent.',
                null=True,
            ),
        ),
    ]
