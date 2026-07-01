from django.db import migrations


def sync_promo_times_used(apps, schema_editor):
    PromoCode = apps.get_model('bookings', 'PromoCode')
    Booking = apps.get_model('bookings', 'Booking')
    for promo in PromoCode.objects.all():
        count = (
            Booking.objects.filter(promo_code_id=promo.pk)
            .exclude(status='cancelled')
            .count()
        )
        if promo.times_used != count:
            promo.times_used = count
            promo.save(update_fields=['times_used'])


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0014_backfill_blockeddate_closure_type'),
    ]

    operations = [
        migrations.RunPython(sync_promo_times_used, migrations.RunPython.noop),
    ]
