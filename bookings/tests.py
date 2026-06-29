from unittest.mock import patch

from django.test import TestCase, override_settings

from bookings.service_area import is_postcode_in_service_area, outward_code


@override_settings(SERVICE_AREA_ENFORCED=True, SERVICE_AREA_NAME='West Yorkshire')
class ServiceAreaTests(TestCase):
    @patch('bookings.service_area.fetch_postcode_info')
    def test_leeds_postcode_allowed(self, mock_fetch):
        mock_fetch.return_value = {'admin_district': 'Leeds'}
        allowed, message = is_postcode_in_service_area('LS1 1AA')
        self.assertTrue(allowed)
        self.assertEqual(message, '')

    @patch('bookings.service_area.fetch_postcode_info')
    def test_sheffield_postcode_rejected(self, mock_fetch):
        mock_fetch.return_value = {'admin_district': 'Sheffield'}
        allowed, message = is_postcode_in_service_area('S1 2HE')
        self.assertFalse(allowed)
        self.assertIn('West Yorkshire', message)

    @patch('bookings.service_area.fetch_postcode_info')
    def test_skipton_postcode_rejected(self, mock_fetch):
        mock_fetch.return_value = {'admin_district': 'Craven'}
        allowed, _ = is_postcode_in_service_area('BD23 1AA')
        self.assertFalse(allowed)

    @patch('bookings.service_area.fetch_postcode_info', return_value=None)
    def test_wakefield_fallback_without_api(self, _mock_fetch):
        allowed, _ = is_postcode_in_service_area('WF1 1AA')
        self.assertTrue(allowed)

    def test_outward_code_normalizes(self):
        self.assertEqual(outward_code('wf1 1aa'), 'WF1')
