from datetime import datetime

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from bookings.models import Booking
from bookings.reminders import (
    bookings_due_for_reminder,
    get_reminder_target_date,
    send_booking_reminder,
)


class Command(BaseCommand):
    help = (
        'Send day-before booking reminder emails (and SMS when Twilio is configured). '
        'Schedule once daily, e.g. 6pm: '
        'docker compose exec web python manage.py send_booking_reminders'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--date',
            help='Appointment date to remind for (YYYY-MM-DD). Default: tomorrow.',
        )
        parser.add_argument(
            '--booking-id',
            type=int,
            help='Send for a single booking ID only (ignores date filter).',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='List matching bookings without sending.',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Send even if a reminder was already sent.',
        )

    def handle(self, *args, **options):
        if not getattr(settings, 'BOOKING_REMINDERS_ENABLED', True):
            self.stdout.write(self.style.WARNING('Booking reminders are disabled (BOOKING_REMINDERS_ENABLED=False).'))
            return

        target_date = None
        if options['date']:
            target_date = datetime.strptime(options['date'], '%Y-%m-%d').date()
        elif not options['booking_id']:
            target_date = get_reminder_target_date()

        if options['booking_id']:
            bookings = (
                Booking.objects.filter(pk=options['booking_id'])
                .select_related('time_slot', 'user')
                .prefetch_related('services')
            )
        else:
            bookings = bookings_due_for_reminder(
                target_date,
                include_sent=options['force'],
            )

        bookings = list(bookings)
        if not bookings:
            label = target_date.isoformat() if target_date else f'booking #{options["booking_id"]}'
            self.stdout.write(f'No bookings due for reminders ({label}).')
            return

        self.stdout.write(
            f'Processing {len(bookings)} booking(s)'
            + (f' for {target_date.isoformat()}' if target_date else '')
            + '…'
        )

        sent = 0
        failed = 0
        for booking in bookings:
            label = (
                f'#{booking.pk} {booking.contact_full_name} — '
                f'{booking.date} {booking.appointment_time_window_display}'
            )
            if options['dry_run']:
                self.stdout.write(f'  [dry-run] Would remind {label}')
                continue

            result = send_booking_reminder(booking, force=options['force'])
            if result.get('skipped'):
                self.stdout.write(self.style.WARNING(f'  Skipped {label}: {result.get("reason")}'))
                continue

            if result.get('marked_sent'):
                sent += 1
                channels = []
                if result.get('email'):
                    channels.append('email')
                if result.get('sms'):
                    channels.append('sms')
                self.stdout.write(self.style.SUCCESS(f'  Reminded {label} ({", ".join(channels) or "no channels"})'))
            else:
                failed += 1
                email = 'ok' if result.get('email') else 'failed'
                sms = result.get('sms')
                sms_label = 'ok' if sms else ('skipped' if sms is None else 'failed')
                self.stdout.write(self.style.ERROR(f'  Failed {label} (email: {email}, sms: {sms_label})'))

        if options['dry_run']:
            return

        summary = f'Done — {sent} sent'
        if failed:
            summary += f', {failed} failed'
        self.stdout.write(self.style.SUCCESS(summary))
