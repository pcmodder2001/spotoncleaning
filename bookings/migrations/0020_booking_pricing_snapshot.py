from decimal import Decimal

from django.db import migrations, models


def backfill_booking_pricing_snapshots(apps, schema_editor):
    Booking = apps.get_model('bookings', 'Booking')
    Service = apps.get_model('services', 'Service')

    for booking in Booking.objects.prefetch_related('services'):
        services = list(booking.services.all())
        if not services and booking.service_id:
            services = list(Service.objects.filter(pk=booking.service_id))

        if not services:
            continue

        items = []
        total = Decimal('0.00')
        for service in services:
            price = Decimal(service.price).quantize(Decimal('0.01'))
            items.append({
                'service_id': service.pk,
                'name': service.name,
                'price': str(price),
            })
            total += price

        booking.subtotal = total.quantize(Decimal('0.01'))
        booking.service_line_items = items
        booking.save(update_fields=['subtotal', 'service_line_items'])


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0019_editablecoverageboundary_postcode_stats'),
    ]

    operations = [
        migrations.AddField(
            model_name='booking',
            name='service_line_items',
            field=models.JSONField(
                blank=True,
                default=list,
                help_text='Per-service price snapshot: [{service_id, name, price}, ...].',
            ),
        ),
        migrations.AddField(
            model_name='booking',
            name='subtotal',
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal('0.00'),
                help_text='Service subtotal at time of booking (snapshot; not affected by catalog price changes).',
                max_digits=8,
            ),
        ),
        migrations.RunPython(
            backfill_booking_pricing_snapshots,
            migrations.RunPython.noop,
        ),
    ]
