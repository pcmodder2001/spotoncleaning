from django.core.management.base import BaseCommand, CommandError

from bookings.followups import (
    booking_completion_date,
    create_followup_from_completed_booking,
    followup_exists_for_booking,
)
from bookings.models import Booking, BookingStatus, CustomerFollowUp


class Command(BaseCommand):
    help = (
        'One-off: create open follow-ups for completed bookings, '
        'using the job completed date as the start of the interval.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--interval',
            type=int,
            default=CustomerFollowUp.IntervalMonths.SIX,
            choices=[choice.value for choice in CustomerFollowUp.IntervalMonths],
            help='Months until the next clean is due (default: 6).',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be created without writing follow-ups.',
        )

    def handle(self, *args, **options):
        interval = options['interval']
        dry_run = options['dry_run']
        valid = {choice.value for choice in CustomerFollowUp.IntervalMonths}
        if interval not in valid:
            raise CommandError('Interval must be 3, 6, 9, or 12 months.')

        bookings = (
            Booking.objects.filter(status=BookingStatus.COMPLETED)
            .select_related('user', 'time_slot')
            .order_by('completed_at', 'date', 'pk')
        )

        created = 0
        skipped = 0
        for booking in bookings:
            if dry_run:
                name = (booking.contact_full_name or '').strip()
                email = (booking.contact_email or '').strip()
                phone = (booking.contact_phone or '').strip()
                if followup_exists_for_booking(booking) or not name or (not email and not phone):
                    skipped += 1
                    continue
                due = CustomerFollowUp.due_date_from_interval(
                    interval,
                    from_date=booking_completion_date(booking),
                )
                created += 1
                self.stdout.write(
                    f'Would create: {name} — due {due} (booking #{booking.pk})'
                )
                continue

            followup = create_followup_from_completed_booking(
                booking,
                interval_months=interval,
            )
            if followup:
                created += 1
                self.stdout.write(
                    f'Created follow-up #{followup.pk} for {followup.name} '
                    f'(due {followup.due_date}, booking #{booking.pk})'
                )
            else:
                skipped += 1

        prefix = 'Would create' if dry_run else 'Created'
        self.stdout.write(self.style.SUCCESS(
            f'{prefix} {created} follow-up(s); skipped {skipped}.'
        ))
