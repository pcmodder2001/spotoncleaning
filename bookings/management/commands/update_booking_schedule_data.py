from django.core.management.base import BaseCommand

from bookings.models import Booking, BookingStatus


class Command(BaseCommand):
    help = 'Backfill geocoding and duration data on existing bookings'

    def handle(self, *args, **options):
        bookings = Booking.objects.exclude(status=BookingStatus.CANCELLED)
        updated = 0
        for booking in bookings:
            service_ids = list(booking.get_services().values_list('pk', flat=True))
            if service_ids:
                booking.geocode_and_set_duration(service_ids)
                updated += 1
                self.stdout.write(
                    f'Booking #{booking.pk}: {booking.date} {booking.time_slot.time} '
                    f'-> {booking.estimated_duration_minutes} min, '
                    f'coords={booking.latitude},{booking.longitude}'
                )
        self.stdout.write(self.style.SUCCESS(f'Updated {updated} booking(s).'))
