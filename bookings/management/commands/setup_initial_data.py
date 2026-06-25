from datetime import time

from django.core.management.base import BaseCommand

from bookings.models import TimeSlot, WeeklySchedule
from services.catalog import sync_service_catalog
from website.models import Testimonial


class Command(BaseCommand):
    help = 'Load initial data for Spot On Appliance Cleaning'

    def handle(self, *args, **options):
        self.stdout.write('Setting up initial data...')

        for day in range(7):
            WeeklySchedule.objects.get_or_create(
                day_of_week=day,
                defaults={'is_available': day < 6},
            )

        slot_times = [
            '08:00', '08:30', '09:00', '09:30', '10:00', '10:30', '11:00', '11:30',
            '12:00', '12:30', '13:00', '13:30', '14:00', '14:30', '15:00', '15:30',
            '16:00', '16:30', '17:00', '17:30',
        ]
        for t in slot_times:
            h, m = map(int, t.split(':'))
            TimeSlot.objects.get_or_create(time=time(h, m))

        sync_service_catalog()

        testimonials = [
            {
                'customer_name': 'Sarah Mitchell',
                'review': 'Absolutely fantastic service! My oven looks brand new. The team was professional and left everything spotless.',
                'rating': 5,
            },
            {
                'customer_name': 'James Thompson',
                'review': 'Great value for money. Booked online easily and they arrived on time. Highly recommend Spot On!',
                'rating': 5,
            },
            {
                'customer_name': 'Emma Davies',
                'review': 'Used them for our range cooker and the difference is incredible. Will definitely book again.',
                'rating': 5,
            },
        ]
        for t in testimonials:
            Testimonial.objects.get_or_create(customer_name=t['customer_name'], defaults=t)

        self.stdout.write(self.style.SUCCESS('Initial data loaded successfully.'))
