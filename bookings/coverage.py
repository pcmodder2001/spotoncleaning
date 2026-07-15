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
    lat = float(info['latitude']) if info and info.get('latitude') is not None else None
    lng = float(info['longitude']) if info and info.get('longitude') is not None else None
    boundaries = get_editable_coverage_boundaries()
    if boundaries and lat is not None and lng is not None:
        covered = point_in_any_boundary(lat, lng)
        matching = []
        enabled_matches = []
    else:
        matching = find_matching_areas(normalized, info, enabled_only=False)
        covered = postcode_is_covered(normalized, info)
        enabled_matches = [area['name'] for area in matching if area['enabled']]

    return {
        'search_type': 'postcode',
        'postcode': normalized,
        'outward': outward,
        'admin_district': (info or {}).get('admin_district') or '',
        'lat': lat,
        'lng': lng,
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
        'enabled_matches': enabled_matches,
    }


EDITABLE_BOUNDARY_SLUG = 'primary'
CACHE_KEY_EDITABLE_BOUNDARIES = 'coverage:editable_boundaries'
BOUNDARY_COLORS = ('#dc2626', '#2563eb', '#059669', '#d97706', '#7c3aed', '#db2777')


def invalidate_editable_boundary_cache():
    cache.delete(CACHE_KEY_EDITABLE_BOUNDARIES)


def _round_coord(value):
    return round(float(value), 6)


def normalize_boundary_ring(ring):
    """Return a cleaned, closed [[lat, lng], ...] ring."""
    if not ring:
        return []

    cleaned = []
    for point in ring:
        if not isinstance(point, (list, tuple)) or len(point) < 2:
            continue
        lat = _round_coord(point[0])
        lng = _round_coord(point[1])
        if cleaned and cleaned[-1][0] == lat and cleaned[-1][1] == lng:
            continue
        cleaned.append([lat, lng])

    if len(cleaned) < 3:
        return []

    if cleaned[0] != cleaned[-1]:
        cleaned.append(cleaned[0])
    return cleaned


def densify_boundary_ring(ring, segments_per_side=5):
    """Add extra vertices along each edge so the shape is easier to drag precisely."""
    normalized = normalize_boundary_ring(ring)
    if len(normalized) < 4:
        return normalized

    vertices = normalized[:-1] if normalized[0] == normalized[-1] else normalized
    if len(vertices) >= segments_per_side * 4:
        return normalized

    dense = []
    for index in range(len(vertices)):
        start = vertices[index]
        end = vertices[(index + 1) % len(vertices)]
        for step in range(segments_per_side):
            t = step / segments_per_side
            dense.append([
                _round_coord(start[0] + (end[0] - start[0]) * t),
                _round_coord(start[1] + (end[1] - start[1]) * t),
            ])
    return normalize_boundary_ring(dense)


def square_boundary_ring(center_lat, center_lng, half_width_km=12.0, segments_per_side=5):
    """Default editable boundary — a square with extra drag points along each edge."""
    import math

    lat = float(center_lat)
    lng = float(center_lng)
    km_per_deg_lat = 111.0
    km_per_deg_lng = 111.0 * math.cos(math.radians(lat))
    d_lat = half_width_km / km_per_deg_lat
    d_lng = half_width_km / km_per_deg_lng
    corners = [
        [lat + d_lat, lng - d_lng],
        [lat + d_lat, lng + d_lng],
        [lat - d_lat, lng + d_lng],
        [lat - d_lat, lng - d_lng],
    ]
    return densify_boundary_ring(corners, segments_per_side=segments_per_side)


def _serialize_editable_boundary(row, index=0):
    return {
        'slug': row.slug,
        'name': row.name,
        'ring': normalize_boundary_ring(row.ring),
        'sort_order': row.sort_order,
        'color': BOUNDARY_COLORS[index % len(BOUNDARY_COLORS)],
        'estimated_postcode_count': int(row.estimated_postcode_count or 0),
        'district_count': int(row.district_count or 0),
        'updated_at': row.updated_at.isoformat() if row.updated_at else '',
    }


def get_editable_coverage_boundaries():
    cached = cache.get(CACHE_KEY_EDITABLE_BOUNDARIES)
    if cached is not None:
        return cached

    from bookings.models import EditableCoverageBoundary

    rows = EditableCoverageBoundary.objects.filter(is_active=True).order_by('sort_order', 'pk')
    payload = [_serialize_editable_boundary(row, index) for index, row in enumerate(rows)]
    cache.set(CACHE_KEY_EDITABLE_BOUNDARIES, payload, CACHE_TTL)
    return payload


def get_editable_coverage_boundary():
    """Backward-compatible helper returning the first saved boundary."""
    boundaries = get_editable_coverage_boundaries()
    if boundaries:
        return boundaries[0]
    return {
        'slug': '',
        'name': 'Service area',
        'ring': [],
        'sort_order': 0,
        'color': BOUNDARY_COLORS[0],
        'estimated_postcode_count': 0,
        'district_count': 0,
        'updated_at': '',
    }


def create_editable_coverage_boundary(center_lat, center_lng):
    import uuid

    from bookings.models import EditableCoverageBoundary

    ring = square_boundary_ring(center_lat, center_lng)
    count = EditableCoverageBoundary.objects.filter(is_active=True).count()
    row = EditableCoverageBoundary.objects.create(
        slug=f'area-{uuid.uuid4().hex[:8]}',
        name=f'Area {count + 1}',
        ring=ring,
        is_active=True,
        sort_order=count,
    )
    invalidate_editable_boundary_cache()
    return _serialize_editable_boundary(row, count)


def save_editable_coverage_boundaries(items):
    from bookings.models import EditableCoverageBoundary
    from bookings.postcode_estimates import refresh_boundary_postcode_stats

    if not items:
        raise ValueError('No boundaries to save.')

    saved = 0
    for item in items:
        slug = (item.get('slug') or '').strip()
        ring = normalize_boundary_ring(item.get('ring', []))
        if not slug or len(ring) < 4:
            continue

        row = EditableCoverageBoundary.objects.filter(slug=slug, is_active=True).first()
        if not row:
            continue

        row.ring = ring
        name = (item.get('name') or '').strip()
        if name:
            row.name = name
        row.save(update_fields=['ring', 'name', 'updated_at'])
        refresh_boundary_postcode_stats(row)
        saved += 1

    if not saved:
        raise ValueError('No valid boundaries to save.')

    invalidate_editable_boundary_cache()
    return get_editable_coverage_boundaries()


def save_editable_coverage_boundary(ring, slug=None):
    """Backward-compatible single-boundary save."""
    target_slug = slug or EDITABLE_BOUNDARY_SLUG
    return save_editable_coverage_boundaries([{'slug': target_slug, 'ring': ring}])


def delete_editable_coverage_boundary(slug):
    from bookings.models import EditableCoverageBoundary

    deleted, _details = EditableCoverageBoundary.objects.filter(slug=slug).delete()
    if deleted:
        invalidate_editable_boundary_cache()
    return deleted


def editable_boundaries_geojson():
    from bookings.coverage_boundaries import ring_to_geojson_polygon

    features = []
    for boundary in get_editable_coverage_boundaries():
        ring = boundary['ring']
        if len(ring) < 4:
            continue
        coordinates = ring_to_geojson_polygon(ring[:-1] if ring[0] == ring[-1] else ring)
        if not coordinates:
            continue
        features.append({
            'type': 'Feature',
            'properties': {
                'slug': boundary['slug'],
                'name': boundary['name'],
                'color': boundary['color'],
                'estimated_postcode_count': boundary['estimated_postcode_count'],
                'district_count': boundary['district_count'],
                'editable': True,
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


def editable_boundary_geojson():
    """Backward-compatible helper returning the first boundary feature."""
    collection = editable_boundaries_geojson()
    features = collection.get('features') or []
    return features[0] if features else None


def point_in_boundary(lat, lng, ring=None):
    """Ray-casting point-in-polygon test for a [[lat, lng], ...] ring."""
    if ring is None:
        return point_in_any_boundary(lat, lng)
    if len(ring) < 4:
        return False

    vertices = ring[:-1] if ring[0] == ring[-1] else ring
    inside = False
    j = len(vertices) - 1
    test_lat = float(lat)
    test_lng = float(lng)

    for i in range(len(vertices)):
        yi, xi = float(vertices[i][0]), float(vertices[i][1])
        yj, xj = float(vertices[j][0]), float(vertices[j][1])
        intersects = (
            (yi > test_lat) != (yj > test_lat)
            and test_lng < (xj - xi) * (test_lat - yi) / ((yj - yi) or 1e-12) + xi
        )
        if intersects:
            inside = not inside
        j = i
    return inside


def point_in_any_boundary(lat, lng):
    """Return True when a point falls inside any saved service boundary."""
    for boundary in get_editable_coverage_boundaries():
        if point_in_boundary(lat, lng, boundary['ring']):
            return True
    return False
