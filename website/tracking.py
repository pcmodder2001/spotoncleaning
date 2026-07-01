import json

from django.conf import settings
from django.utils import timezone

ATTRIBUTION_KEYS = ('utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'fbclid')
FACEBOOK_SOURCE_TOKENS = ('facebook', 'fb', 'meta', 'instagram', 'ig')


def meta_pixel_enabled(request):
    pixel_id = getattr(settings, 'META_PIXEL_ID', '')
    if not pixel_id:
        return False
    path = getattr(request, 'path', '') or ''
    return not path.startswith('/panel/')


def capture_marketing_attribution(request):
    """First-touch: remember ad click params from the landing URL in session."""
    if not hasattr(request, 'session'):
        return
    if request.session.get('marketing_attribution'):
        return

    data = {}
    for key in ATTRIBUTION_KEYS:
        value = request.GET.get(key, '').strip()
        if value:
            data[key] = value[:255]
    if not data:
        return

    data['captured_at'] = timezone.now().isoformat()
    request.session['marketing_attribution'] = data
    request.session.modified = True


def get_marketing_attribution(request):
    if not hasattr(request, 'session'):
        return {}
    return dict(request.session.get('marketing_attribution') or {})


def apply_marketing_attribution(instance, request):
    data = get_marketing_attribution(request)
    if data and not instance.marketing_attribution:
        instance.marketing_attribution = data
        instance.save(update_fields=['marketing_attribution'])


def is_facebook_attribution(attribution):
    if not attribution:
        return False
    if attribution.get('fbclid'):
        return True
    source = (attribution.get('utm_source') or '').lower()
    return any(token in source for token in FACEBOOK_SOURCE_TOKENS)


def attribution_label(attribution):
    if not attribution:
        return 'Direct / unknown'
    if attribution.get('fbclid'):
        parts = ['Facebook']
        if attribution.get('utm_campaign'):
            parts.append(attribution['utm_campaign'])
        return ' · '.join(parts)
    source = (attribution.get('utm_source') or '').strip()
    if source:
        label = source.replace('_', ' ').replace('-', ' ').title()
        campaign = (attribution.get('utm_campaign') or '').strip()
        if campaign:
            return f'{label} · {campaign}'
        return label
    return 'Direct / unknown'


def queue_meta_pixel_event(request, event_name, **params):
    """Queue a one-time Meta Pixel event for the next public page load."""
    if not meta_pixel_enabled(request):
        return
    events = request.session.get('meta_pixel_events', [])
    events.append({
        'name': event_name,
        'params_json': json.dumps(params),
    })
    request.session['meta_pixel_events'] = events
    request.session.modified = True


def pop_meta_pixel_events(request):
    if not meta_pixel_enabled(request):
        return []
    return request.session.pop('meta_pixel_events', [])
