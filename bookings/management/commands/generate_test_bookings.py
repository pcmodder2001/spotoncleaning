import random
from datetime import datetime, timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from bookings.management.commands.test_booking_data import (
    FIRST_NAMES,
    LAST_NAMES,
    SAMPLE_JOBS,
    TEST_EMAIL_DOMAIN,
)
from bookings.models import Booking, BookingStatus, TimeSlot
from bookings.scheduling import get_feasible_slots
from services.models import Service, ServiceType


class Command(BaseCommand):
    help = 'Generate random test bookings for schedule, map, and routing testing'

    def add_arguments(self, parser):
        parser.add_argument(
            '--count',
            type=int,
            default=8,
            help='Number of bookings to create (default: 8)',
        )
        parser.add_argument(
            '--date',
            type=str,
            help='Put all jobs on this date (YYYY-MM-DD). Default: spread from tomorrow',
        )
        parser.add_argument(
            '--days',
            type=int,
            default=1,
            help='Spread jobs across this many days starting from --date or tomorrow (default: 1)',
        )
        parser.add_argument(
            '--status',
            type=str,
            default='confirmed',
            choices=[choice[0] for choice in BookingStatus.choices],
            help='Booking status for generated jobs (default: confirmed)',
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help=f'Remove existing test bookings (@{TEST_EMAIL_DOMAIN}) and exit',
        )
        parser.add_argument(
            '--seed',
            type=int,
            default=42,
            help='Random seed for repeatable results (default: 42)',
        )

    def handle(self, *args, **options):
        if options['clear']:
            deleted, _ = Booking.objects.filter(guest_email__iendswith=f'@{TEST_EMAIL_DOMAIN}').delete()
            self.stdout.write(self.style.SUCCESS(f'Removed {deleted} test booking(s).'))
            return

        count = options['count']
        if count < 1:
            raise CommandError('--count must be at least 1')

        random.seed(options['seed'])

        oven_services = list(Service.objects.filter(active=True, service_type=ServiceType.OVEN))
        addon_services = list(Service.objects.filter(active=True, service_type=ServiceType.ADDON))
        if not oven_services:
            raise CommandError('No active oven services found. Run: python manage.py setup_initial_data')

        if not TimeSlot.objects.filter(active=True).exists():
            raise CommandError('No active time slots found. Run: python manage.py setup_initial_data')

        start_date = self._parse_start_date(options['date'])
        dates = [start_date + timedelta(days=offset) for offset in range(options['days'])]
        status = options['status']

        created = 0
        skipped = 0
        used_emails = set(
            Booking.objects.filter(guest_email__iendswith=f'@{TEST_EMAIL_DOMAIN}').values_list(
                'guest_email', flat=True
            )
        )

        locations = SAMPLE_JOBS.copy()
        random.shuffle(locations)

        self.stdout.write(
            f'Creating up to {count} test booking(s) across '
            f'{len(dates)} day(s) starting {start_date}…'
        )

        with transaction.atomic():
            for index in range(count):
                address_line, city, postcode = locations[index % len(locations)]
                job_date = dates[index % len(dates)]

                services = [random.choice(oven_services)]
                if addon_services and random.random() < 0.45:
                    services.append(random.choice(addon_services))

                service_ids = [service.pk for service in services]
                feasible = list(
                    get_feasible_slots(job_date, service_ids=service_ids, postcode=postcode, city=city)
                )
                if not feasible:
                    skipped += 1
                    self.stdout.write(
                        self.style.WARNING(
                            f'  Skipped — no feasible slot on {job_date} for {postcode}'
                        )
                    )
                    continue

                time_slot = random.choice(feasible[: max(1, len(feasible) // 2)])

                first = random.choice(FIRST_NAMES)
                last = random.choice(LAST_NAMES)
                email = self._unique_email(first, last, index, used_emails)

                booking = Booking.objects.create(
                    guest_first_name=first,
                    guest_last_name=last,
                    guest_email=email,
                    guest_phone=f'07{random.randint(100000000, 999999999)}',
                    date=job_date,
                    time_slot=time_slot,
                    address_line_1=address_line,
                    city=city,
                    postcode=postcode,
                    notes='TEST BOOKING — safe to delete',
                    access_instructions=random.choice([
                        '',
                        'Key under mat',
                        'Ring doorbell — dog friendly',
                        'Park on street',
                    ]),
                    status=status,
                )
                booking.services.set(services)
                booking.geocode_and_set_duration(service_ids)

                created += 1
                self.stdout.write(
                    f'  #{booking.pk} {job_date} {time_slot.time:%H:%M} '
                    f'{first} {last} — {city} ({postcode}) — {booking.service_summary}'
                )

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(f'Created {created} test booking(s).'))
        if skipped:
            self.stdout.write(self.style.WARNING(f'Skipped {skipped} (no feasible slot).'))
        self.stdout.write(
            f'View schedule: /panel/schedule/?date={start_date.isoformat()}'
        )
        self.stdout.write(
            f'Clear later: python manage.py generate_test_bookings --clear'
        )

    def _parse_start_date(self, date_str):
        if date_str:
            try:
                return datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError as exc:
                raise CommandError('--date must be YYYY-MM-DD') from exc
        return timezone.localdate() + timedelta(days=1)

    def _unique_email(self, first, last, index, used_emails):
        base = f'{first}.{last}.{index}'.lower().replace(' ', '')
        email = f'{base}@{TEST_EMAIL_DOMAIN}'
        counter = 1
        while email in used_emails:
            email = f'{base}.{counter}@{TEST_EMAIL_DOMAIN}'
            counter += 1
        used_emails.add(email)
        return email
