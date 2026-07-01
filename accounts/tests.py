from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from accounts.addresses import import_addresses_from_bookings, save_address_for_user
from accounts.models import SavedAddress
from bookings.models import Booking, BookingStatus, TimeSlot

User = get_user_model()


@override_settings(SERVICE_AREA_ENFORCED=False)
class SavedAddressTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='customer@example.com',
            password='test-pass-123',
            first_name='Test',
            last_name='Customer',
        )
        self.slot = TimeSlot.objects.create(time='09:00:00')

    def test_import_addresses_from_bookings(self):
        Booking.objects.create(
            user=self.user,
            date='2026-08-01',
            time_slot=self.slot,
            status=BookingStatus.CONFIRMED,
            address_line_1='1 Test Street',
            city='Wakefield',
            postcode='WF1 1AA',
        )
        created = import_addresses_from_bookings(self.user)
        self.assertEqual(created, 1)
        address = SavedAddress.objects.get(user=self.user)
        self.assertTrue(address.is_default)
        self.assertEqual(import_addresses_from_bookings(self.user), 0)

    def test_save_address_deduplicates(self):
        address, created = save_address_for_user(
            self.user,
            label='Home',
            address_line_1='1 Test Street',
            city='Wakefield',
            postcode='WF1 1AA',
            is_default=True,
        )
        self.assertTrue(created)
        again, created_again = save_address_for_user(
            self.user,
            label='Home',
            address_line_1='1 Test Street',
            city='Wakefield',
            postcode='WF1 1AA',
        )
        self.assertFalse(created_again)
        self.assertEqual(address.pk, again.pk)
        self.assertEqual(SavedAddress.objects.filter(user=self.user).count(), 1)
