from django.db import migrations


def backfill_closure_types(apps, schema_editor):
    BlockedDate = apps.get_model('bookings', 'BlockedDate')
    for blocked in BlockedDate.objects.all():
        reason = (blocked.reason or '').lower()
        if 'fully booked' in reason or reason == 'full':
            if blocked.closure_type != 'full':
                blocked.closure_type = 'full'
                blocked.save(update_fields=['closure_type'])


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0013_blockeddate_closure_type'),
    ]

    operations = [
        migrations.RunPython(backfill_closure_types, migrations.RunPython.noop),
    ]
