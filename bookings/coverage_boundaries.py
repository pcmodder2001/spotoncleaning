"""Local authority boundary polygons for the coverage map."""

import json
import math
from functools import lru_cache
from pathlib import Path

DATA_PATH = Path(__file__).resolve().parent / 'data' / 'coverage_boundaries.json'

# Slugs that use a full council-district outline from coverage_boundaries.json.
LAD_BOUNDARY_SLUGS = frozenset({
    'leeds',
    'wakefield',
    'bradford',
    'york',
    'harrogate',
    'selby',
    'halifax',
    'huddersfield',
    'barnsley',
})

# Borough slug -> JSON boundary key when the names differ.
LAD_BOUNDARY_KEYS = {
    'halifax': 'calderdale',
    'huddersfield': 'kirklees',
}


@lru_cache(maxsize=1)
def _load_boundaries():
    if not DATA_PATH.exists():
        return {}
    return json.loads(DATA_PATH.read_text(encoding='utf-8'))


def boundary_key_for_slug(slug):
    if slug not in LAD_BOUNDARY_SLUGS:
        return ''
    return LAD_BOUNDARY_KEYS.get(slug, slug)


def get_boundary_ring(boundary_key):
    """Return [[lat, lng], ...] outer ring for a boundary key."""
    if not boundary_key:
        return []
    return _load_boundaries().get(boundary_key) or []


def circle_boundary_ring(center_lat, center_lng, radius_km, points=36):
    """Approximate a town area as a polygon circle."""
    if radius_km <= 0:
        return []
    lat = float(center_lat)
    lng = float(center_lng)
    km_per_deg_lat = 111.0
    km_per_deg_lng = 111.0 * math.cos(math.radians(lat))
    ring = []
    for index in range(points + 1):
        angle = 2 * math.pi * index / points
        ring.append([
            round(lat + (radius_km / km_per_deg_lat) * math.sin(angle), 5),
            round(lng + (radius_km / km_per_deg_lng) * math.cos(angle), 5),
        ])
    return ring


def boundary_ring_for_area(area):
    """District outline for boroughs; local circle for towns and sub-areas."""
    ring = get_boundary_ring(boundary_key_for_slug(area['slug']))
    if ring:
        return ring, 'district'
    ring = circle_boundary_ring(
        float(area['center_lat']),
        float(area['center_lng']),
        float(area['map_radius_km']),
    )
    return ring, 'local'


def ring_to_geojson_polygon(ring):
    """Convert [[lat, lng], ...] to GeoJSON polygon coordinates [[[lng, lat], ...]]."""
    if not ring:
        return []
    return [[[lng, lat] for lat, lng in ring]]


def available_boundary_keys():
    return list(_load_boundaries().keys())
