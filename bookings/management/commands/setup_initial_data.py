from datetime import time

from django.core.management.base import BaseCommand

from bookings.models import TimeSlot, WeeklySchedule
from services.models import Service, ServiceType
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

        service_durations = {
            'Standard Oven (with Grill)': 60,
            'Double Oven': 90,
            'Aga Cooker': 120,
            'Hob': 30,
            'Extractor Fan': 30,
        }
        services = [
            {
                'name': 'Standard Oven (with Grill)',
                'description': 'Deep clean of a single oven with grill — racks, door glass, and interior surfaces.',
                'price': 59.00,
                'sort_order': 1,
                'service_type': ServiceType.OVEN,
                'exclusive_group': 'oven',
            },
            {
                'name': 'Double Oven',
                'description': 'Complete cleaning of double ovens including both cavities, racks, and door panels.',
                'price': 89.00,
                'sort_order': 2,
                'service_type': ServiceType.OVEN,
                'exclusive_group': 'oven',
            },
            {
                'name': 'Aga Cooker',
                'description': 'Specialist cleaning for Aga cookers — ovens, hotplates, and enamel surfaces restored to shine.',
                'price': 119.00,
                'sort_order': 3,
                'service_type': ServiceType.OVEN,
                'exclusive_group': 'oven',
            },
            {
                'name': 'Hob',
                'description': 'Thorough hob cleaning removing grease, burnt-on food, and restoring shine.',
                'price': 39.00,
                'sort_order': 4,
                'service_type': ServiceType.ADDON,
                'exclusive_group': '',
            },
            {
                'name': 'Extractor Fan',
                'description': 'Cleaning of extractor fan units, filters, and surrounding areas for improved airflow.',
                'price': 35.00,
                'sort_order': 5,
                'service_type': ServiceType.ADDON,
                'exclusive_group': '',
            },
        ]
        for s in services:
            s['duration_minutes'] = service_durations.get(s['name'], 60)
            Service.objects.update_or_create(name=s['name'], defaults=s)

        # Deactivate legacy service names if they exist
        legacy_names = ['Single Oven Cleaning', 'Range Cooker Cleaning', 'Hob Cleaning', 'Extractor Fan Cleaning', 'Double Oven Cleaning']
        Service.objects.filter(name__in=legacy_names).update(active=False)

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
