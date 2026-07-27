from decimal import Decimal

from django.test import TestCase, override_settings

from bookings.forms import BookingForm, GuestBookingForm
from bookings.models import Booking, BookingStatus, PromoCode, TimeSlot
from bookings.promo import PromoError, get_valid_promo, record_promo_use, release_promo_use
from bookings.utils import cancel_booking
from services.models import Service, ServiceType


@override_settings(SERVICE_AREA_ENFORCED=False)
class PromoUsageTests(TestCase):
    def setUp(self):
        self.slot = TimeSlot.objects.create(time='10:00:00')
        self.service = Service.objects.create(
            name='Single oven',
            description='Test',
            price=Decimal('60.00'),
            service_type=ServiceType.OVEN,
            duration_minutes=60,
        )
        self.promo = PromoCode.objects.create(
            code='TEST1',
            discount_type=PromoCode.DiscountType.FIXED,
            discount_value=Decimal('10.00'),
            max_uses=1,
        )

    def _booking_form_data(self, **extra):
        data = {
            'services': [str(self.service.pk)],
            'date': '2026-09-01',
            'time_slot': str(self.slot.pk),
            'address_line_1': '1 Test Street',
            'city': 'Wakefield',
            'postcode': 'WF1 1AA',
            'promo_code': 'TEST1',
            'notes': '',
        }
        data.update(extra)
        return data

    def test_record_promo_use_increments_counter(self):
        record_promo_use(self.promo)
        self.promo.refresh_from_db()
        self.assertEqual(self.promo.times_used, 1)

    def test_record_promo_use_blocks_when_limit_reached(self):
        record_promo_use(self.promo)
        with self.assertRaises(PromoError):
            get_valid_promo('TEST1')

    def test_guest_booking_form_does_not_increment_promo_itself(self):
        form = GuestBookingForm(data={
            **self._booking_form_data(),
            'guest_first_name': 'Guest',
            'guest_last_name': 'User',
            'guest_email': 'guest@example.com',
            'accept_terms': True,
        })
        self.assertTrue(form.is_valid())
        booking = form.save()
        self.promo.refresh_from_db()
        self.assertEqual(self.promo.times_used, 0)
        self.assertEqual(booking.promo_code_id, self.promo.pk)

    def test_cancel_booking_releases_promo_use(self):
        record_promo_use(self.promo)
        booking = Booking.objects.create(
            date='2026-09-01',
            time_slot=self.slot,
            status=BookingStatus.PENDING,
            address_line_1='1 Test Street',
            city='Wakefield',
            postcode='WF1 1AA',
            promo_code=self.promo,
            discount_amount=Decimal('10.00'),
        )
        booking.services.add(self.service)
        cancel_booking(booking, notify=False)
        self.promo.refresh_from_db()
        self.assertEqual(self.promo.times_used, 0)
        self.assertTrue(get_valid_promo('TEST1'))

    def test_booking_form_validates_usage_limit(self):
        record_promo_use(self.promo)
        form = BookingForm(data=self._booking_form_data())
        self.assertFalse(form.is_valid())


@override_settings(SERVICE_AREA_ENFORCED=False)
class AutoPromoTests(TestCase):
    def setUp(self):
        self.slot = TimeSlot.objects.create(time='10:00:00')
        self.oven_a = Service.objects.create(
            name='Single oven',
            description='Test',
            price=Decimal('60.00'),
            service_type=ServiceType.OVEN,
            duration_minutes=60,
        )
        self.oven_b = Service.objects.create(
            name='Double oven',
            description='Test',
            price=Decimal('80.00'),
            service_type=ServiceType.OVEN,
            duration_minutes=90,
            exclusive_group='oven',
        )
        self.addon = Service.objects.create(
            name='Hob',
            description='Test',
            price=Decimal('25.00'),
            service_type=ServiceType.ADDON,
            duration_minutes=30,
        )
        self.auto_promo = PromoCode.objects.create(
            code='MULTI10',
            description='10% off when you book 2 or more appliances',
            discount_type=PromoCode.DiscountType.PERCENT,
            discount_value=Decimal('10.00'),
            auto_apply=True,
            min_appliance_count=2,
        )

    def test_auto_promo_not_applied_for_single_appliance(self):
        from bookings.promo import get_auto_promo_for_services

        self.assertIsNone(get_auto_promo_for_services([self.oven_a]))

    def test_auto_promo_applied_for_two_appliances(self):
        from bookings.promo import get_auto_promo_for_services

        promo = get_auto_promo_for_services([self.oven_a, self.oven_b])
        self.assertEqual(promo.pk, self.auto_promo.pk)
        self.assertEqual(promo.calculate_discount(Decimal('140.00')), Decimal('14.00'))

    def test_addons_do_not_count_toward_appliance_minimum(self):
        from bookings.promo import get_auto_promo_for_services

        self.assertIsNone(get_auto_promo_for_services([self.oven_a, self.addon]))

    def test_booking_form_applies_auto_promo_without_code(self):
        form = BookingForm(data={
            'services': [str(self.oven_a.pk), str(self.oven_b.pk)],
            'date': '2026-09-01',
            'time_slot': str(self.slot.pk),
            'address_line_1': '1 Test Street',
            'city': 'Wakefield',
            'postcode': 'WF1 1AA',
            'promo_code': '',
            'notes': '',
        })
        self.assertTrue(form.is_valid(), form.errors)
        booking = form.save()
        self.assertEqual(booking.promo_code_id, self.auto_promo.pk)
        self.assertEqual(booking.discount_amount, Decimal('14.00'))
