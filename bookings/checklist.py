"""Default on-site job checklist for admin panel."""

DEFAULT_JOB_CHECKLIST = [
    {'key': 'access_confirmed', 'label': 'Access confirmed with customer', 'done': False},
    {'key': 'oven_pre_photo', 'label': 'Before photo taken', 'done': False},
    {'key': 'oven_cleaned', 'label': 'Oven deep clean completed', 'done': False},
    {'key': 'hob_cleaned', 'label': 'Hob cleaned (if booked)', 'done': False},
    {'key': 'extractor_cleaned', 'label': 'Extractor cleaned (if booked)', 'done': False},
    {'key': 'oven_post_photo', 'label': 'After photo taken', 'done': False},
    {'key': 'area_tidy', 'label': 'Work area left tidy', 'done': False},
    {'key': 'customer_walkthrough', 'label': 'Customer walkthrough done', 'done': False},
]


def merge_checklist(stored):
    """Merge stored checklist state with default template keys."""
    stored = stored or {}
    merged = []
    for item in DEFAULT_JOB_CHECKLIST:
        key = item['key']
        merged.append({
            'key': key,
            'label': item['label'],
            'done': bool(stored.get(key, item['done'])),
        })
    return merged


def checklist_from_post(post_data):
    """Build checklist dict from POST checkboxes named checklist_<key>."""
    result = {}
    for item in DEFAULT_JOB_CHECKLIST:
        key = item['key']
        result[key] = post_data.get(f'checklist_{key}') == 'on'
    return result
