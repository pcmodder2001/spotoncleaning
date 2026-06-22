
from django.db import migrations


def copy_service_to_services(apps, schema_editor):
    Booking = apps.get_model('bookings', 'Booking')
    for booking in Booking.objects.exclude(service_id__isnull=True):
        booking.services.add(booking.service_id)


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0002_booking_services_alter_booking_service'),
    ]

    operations = [
        migrations.RunPython(copy_service_to_services, migrations.RunPython.noop),
    ]
