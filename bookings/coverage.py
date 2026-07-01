"""Coverage area helpers for the admin map and booking validation."""

import re

from django.core.cache import cache

from bookings.coverage_data import EXCLUDED_POSTCODE_DISTRICTS
from bookings.models import CoverageArea
from bookings.routing import normalize_postcode

CACHE_KEY_ENABLED = 'coverage:areas:enabled'
CACHE_KEY_ALL = 'coverage:areas:all'
CACHE_TTL = 300

EXCLUDED_OUTWARD_CODES = frozenset(item['code'] for item in EXCLUDED_POSTCODE_DISTRICTS)

_AREA_FIELDS = (
    'slug',
    'name',
    'region_group',
    'admin_districts',
    'postcode_districts',
    'postcode_area',
    'enabled',
    'map_color',
    'center_lat',
    'center_lng',
    'map_radius_km',
)


def invalidate_coverage_cache():
    cache.delete(CACHE_KEY_ENABLED)
    cache.delete(CACHE_KEY_ALL)


def _serialize_area(area):
    return {
        'slug': area['slug'],
        'name': area['name'],
        'region_group': area['region_group'],
        'admin_districts': area['admin_districts'] or [],
        'postcode_districts': area['postcode_districts'] or [],
        'postcode_area': area['postcode_area'] or '',
        'enabled': area['enabled'],
        'map_color': area['map_color'],
        'center_lat': area['center_lat'],
        'center_lng': area['center_lng'],
        'map_radius_km': area['map_radius_km'],
    }


def get_all_coverage_areas():
    cached = cache.get(CACHE_KEY_ALL)
    if cached is not None:
        return cached
    areas = [
        _serialize_area(row)
        for row in CoverageArea.objects.all().order_by('sort_order', 'name').values(*_AREA_FIELDS)
    ]
    cache.set(CACHE_KEY_ALL, areas, CACHE_TTL)
    return areas


def get_enabled_coverage_areas():
    cached = cache.get(CACHE_KEY_ENABLED)
    if cached is not None:
        return cached
    areas = [
        _serialize_area(row)
        for row in CoverageArea.objects.filter(enabled=True).order_by('sort_order', 'name').values(*_AREA_FIELDS)
    ]
    cache.set(CACHE_KEY_ENABLED, areas, CACHE_TTL)
    return areas


def outward_code(postcode):
    normalized = normalize_postcode(postcode)
    if not normalized:
        return ''
    return normalized.split()[0].upper()


def _postcode_area_letters(outward):
    match = re.match(r'^([A-Z]+)', outward)
    return match.group(1) if match else ''


def area_matches_postcode(area, outward, admin_district=''):
    if outward in EXCLUDED_OUTWARD_CODES:
        return False
    districts = area.get('postcode_districts') or []
    if districts:
        return outward in districts
    admins = area.get('admin_districts') or []
    if admins and admin_district in admins:
        return True
    postcode_area = (area.get('postcode_area') or '').upper()
    if postcode_area and _postcode_area_letters(outward) == postcode_area:
        return True
    return False


def find_matching_areas(postcode, info=None, *, enabled_only=False):
    outward = outward_code(postcode)
    admin_district = (info or {}).get('admin_district') or ''
    areas = get_enabled_coverage_areas() if enabled_only else get_all_coverage_areas()
    return [
        area for area in areas
        if area_matches_postcode(area, outward, admin_district)
    ]


def postcode_is_covered(postcode, info=None):
    if outward_code(postcode) in EXCLUDED_OUTWARD_CODES:
        return False
    return bool(find_matching_areas(postcode, info, enabled_only=True))


def coverage_areas_for_map():
    from bookings.coverage_boundaries import boundary_ring_for_area, ring_to_geojson_polygon

    features = []
    for area in get_all_coverage_areas():
        ring, boundary_type = boundary_ring_for_area(area)
        coordinates = ring_to_geojson_polygon(ring)
        if not coordinates:
            continue
        features.append({
            'type': 'Feature',
            'properties': {
                'slug': area['slug'],
                'slugs': [area['slug']],
                'name': area['name'],
                'names': [area['name']],
                'region_group': area['region_group'],
                'enabled': area['enabled'],
                'color': area['map_color'],
                'postcode_label': _area_postcode_label(area),
                'boundary_type': boundary_type,
            },
            'geometry': {
                'type': 'Polygon',
                'coordinates': coordinates,
            },
        })
    return {
        'type': 'FeatureCollection',
        'features': features,
    }


def _area_postcode_label(area):
    if area['postcode_districts']:
        districts = area['postcode_districts']
        if len(districts) <= 4:
            return ', '.join(districts)
        return f'{districts[0]}-{districts[-1]} ({len(districts)} districts)'
    if area['postcode_area']:
        return f"{area['postcode_area']} postcodes"
    if area['admin_districts']:
        return area['admin_districts'][0]
    return 'Custom area'


def set_coverage_area_enabled(slug, enabled):
    updated = CoverageArea.objects.filter(slug=slug).update(enabled=enabled)
    if updated:
        invalidate_coverage_cache()
    return updated


def set_region_enabled(region_group, enabled):
    updated = CoverageArea.objects.filter(region_group=region_group).update(enabled=enabled)
    if updated:
        invalidate_coverage_cache()
    return updated


def find_areas_by_name(query):
    needle = query.lower().strip()
    if not needle:
        return []
    ranked = []
    for area in get_all_coverage_areas():
        name = area['name'].lower()
        slug_label = area['slug'].replace('-', ' ')
        region = area['region_group'].lower()
        if needle == name:
            score = 0
        elif needle == slug_label:
            score = 1
        elif name.startswith(needle):
            score = 2
        elif needle in name:
            score = 3
        elif needle in slug_label:
            score = 4
        elif needle in region:
            score = 5
        else:
            continue
        ranked.append((score, area['name'], area))
    ranked.sort(key=lambda item: (item[0], item[1]))
    return [area for *_rest, area in ranked]


def lookup_area_on_map(query):
    matches = find_areas_by_name(query)
    if not matches:
        return None
    area = matches[0]
    return {
        'search_type': 'area',
        'query': query.strip(),
        'postcode': '',
        'outward': '',
        'admin_district': '',
        'lat': float(area['center_lat']),
        'lng': float(area['center_lng']),
        'covered': area['enabled'],
        'excluded': False,
        'in_catalog': True,
        'area_slug': area['slug'],
        'area_name': area['name'],
        'matching_areas': [
            {
                'slug': item['slug'],
                'name': item['name'],
                'region_group': item['region_group'],
                'enabled': item['enabled'],
            }
            for item in matches
        ],
        'enabled_matches': [item['name'] for item in matches if item['enabled']],
    }


def _looks_like_postcode(query):
    compact = re.sub(r'\s+', '', query.upper())
    if not compact or not any(ch.isdigit() for ch in compact):
        return False
    normalized = normalize_postcode(query)
    return bool(normalized and outward_code(normalized))


def lookup_place_on_map(query):
    from bookings.routing import geocode_place_name

    place = geocode_place_name(query)
    if not place:
        return None
    return {
        'search_type': 'place',
        'query': query.strip(),
        'postcode': '',
        'outward': '',
        'admin_district': '',
        'lat': place['lat'],
        'lng': place['lng'],
        'covered': False,
        'excluded': False,
        'in_catalog': False,
        'area_slug': '',
        'area_name': place['name'],
        'matching_areas': [],
        'enabled_matches': [],
    }


def lookup_coverage_search(query):
    cleaned = query.strip()
    if not cleaned:
        return {'error': 'Enter a postcode or area name.'}

    if _looks_like_postcode(cleaned):
        normalized = normalize_postcode(cleaned)
        result = lookup_postcode_on_map(normalized)
        result['search_type'] = 'postcode'
        result['query'] = cleaned
        result['area_slug'] = ''
        result['area_name'] = ''
        return result

    area_result = lookup_area_on_map(cleaned)
    if area_result:
        area_result['in_catalog'] = True
        return area_result

    place_result = lookup_place_on_map(cleaned)
    if place_result:
        return place_result

    return {'error': f'No area or postcode matched "{cleaned}".', 'query': cleaned}


def lookup_postcode_on_map(postcode):
    from bookings.routing import fetch_postcode_info

    normalized = normalize_postcode(postcode)
    outward = outward_code(normalized)
    info = fetch_postcode_info(normalized) if normalized else None
    matching = find_matching_areas(normalized, info, enabled_only=False)
    covered = postcode_is_covered(normalized, info)
    enabled_matches = [area for area in matching if area['enabled']]

    return {
        'search_type': 'postcode',
        'postcode': normalized,
        'outward': outward,
        'admin_district': (info or {}).get('admin_district') or '',
        'lat': float(info['latitude']) if info and info.get('latitude') is not None else None,
        'lng': float(info['longitude']) if info and info.get('longitude') is not None else None,
        'covered': covered,
        'excluded': outward in EXCLUDED_OUTWARD_CODES,
        'area_slug': '',
        'area_name': '',
        'matching_areas': [
            {
                'slug': area['slug'],
                'name': area['name'],
                'region_group': area['region_group'],
                'enabled': area['enabled'],
            }
            for area in matching
        ],
        'enabled_matches': [area['name'] for area in enabled_matches],
    }
