import base64
import json
import logging
import re
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings

logger = logging.getLogger(__name__)


def sms_is_configured():
    return bool(
        getattr(settings, 'TWILIO_ACCOUNT_SID', '')
        and getattr(settings, 'TWILIO_AUTH_TOKEN', '')
        and getattr(settings, 'TWILIO_FROM_NUMBER', '')
    )


def normalize_phone_number(raw_number):
    """Return an E.164-style number when possible (UK-focused)."""
    if not raw_number:
        return ''

    digits = re.sub(r'[^\d+]', '', raw_number.strip())
    if not digits:
        return ''

    if digits.startswith('+'):
        return digits

    if digits.startswith('00'):
        return '+' + digits[2:]

    if digits.startswith('0'):
        return '+44' + digits[1:]

    if len(digits) == 10 and digits.startswith('7'):
        return '+44' + digits

    return '+' + digits


def send_sms_message(to_number, body):
    """Send an SMS via Twilio. Returns (success, detail)."""
    if not getattr(settings, 'SMS_ENABLED', False):
        return False, 'SMS not configured'

    normalized = normalize_phone_number(to_number)
    if not normalized:
        return False, 'Invalid phone number'

    payload = urllib.parse.urlencode({
        'To': normalized,
        'From': settings.TWILIO_FROM_NUMBER,
        'Body': body.strip(),
    }).encode('utf-8')

    url = (
        f'https://api.twilio.com/2010-04-01/Accounts/'
        f'{settings.TWILIO_ACCOUNT_SID}/Messages.json'
    )
    credentials = base64.b64encode(
        f'{settings.TWILIO_ACCOUNT_SID}:{settings.TWILIO_AUTH_TOKEN}'.encode('utf-8')
    ).decode('ascii')

    request = urllib.request.Request(
        url,
        data=payload,
        method='POST',
        headers={
            'Authorization': f'Basic {credentials}',
            'Content-Type': 'application/x-www-form-urlencoded',
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            response.read()
        return True, normalized
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode('utf-8', errors='replace')
        try:
            detail = json.loads(detail).get('message', detail)
        except json.JSONDecodeError:
            pass
        logger.exception('Twilio SMS failed for %s: %s', normalized, detail)
        return False, detail
    except Exception as exc:
        logger.exception('Twilio SMS failed for %s', normalized)
        return False, str(exc)
