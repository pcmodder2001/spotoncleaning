"""Estimate how many UK postcodes fall inside a service boundary."""

import logging
import math
import time

from bookings.coverage import normalize_boundary_ring, outward_code, point_in_boundary
from bookings.routing import fetch_postcodes_near_location

logger = logging.getLogger(__name__)

MAX_SAMPLE_POINTS = 24
SAMPLE_SPACING_KM = 2.5
SAMPLE_RADIUS_M = 3500
SAMPLE_LIMIT = 100
API_PAUSE_SECONDS = 0.05


def _ring_bounds(ring):
    vertices = ring[:-1] if len(ring) > 1 and ring[0] == ring[-1] else ring
    lats = [float(point[0]) for point in vertices]
    lngs = [float(point[1]) for point in vertices]
    return min(lats), min(lngs), max(lats), max(lngs)


def _grid_sample_points(ring, spacing_km=SAMPLE_SPACING_KM, max_points=MAX_SAMPLE_POINTS):
    normalized = normalize_boundary_ring(ring)
    if len(normalized) < 4:
        return []

    min_lat, min_lng, max_lat, max_lng = _ring_bounds(normalized)
    center_lat = (min_lat + max_lat) / 2
    km_per_deg_lat = 111.0
    km_per_deg_lng = 111.0 * math.cos(math.radians(center_lat))
    step_lat = spacing_km / km_per_deg_lat
    step_lng = spacing_km / km_per_deg_lng

    points = []
    lat = min_lat
    while lat <= max_lat + 1e-9:
        lng = min_lng
        while lng <= max_lng + 1e-9:
            if point_in_boundary(lat, lng, normalized):
                points.append((lat, lng))
                if len(points) >= max_points:
                    return points
            lng += step_lng
        lat += step_lat

    if not points:
        points.append((center_lat, (min_lng + max_lng) / 2))
    return points


def estimate_postcodes_in_ring(ring):
    """
    Rough postcode estimate for a boundary polygon.

    Uses a sample grid plus postcodes.io nearby lookups, then counts unique
    postcodes whose coordinates fall inside the boundary.
    """
    normalized = normalize_boundary_ring(ring)
    if len(normalized) < 4:
        return {
            'postcode_count': 0,
            'district_count': 0,
            'sample_points': 0,
        }

    sample_points = _grid_sample_points(normalized)
    postcodes = {}
    districts = set()

    for lat, lng in sample_points:
        nearby = fetch_postcodes_near_location(
            lat,
            lng,
            radius_m=SAMPLE_RADIUS_M,
            limit=SAMPLE_LIMIT,
        )
        for item in nearby:
            postcode = item.get('postcode')
            item_lat = item.get('latitude')
            item_lng = item.get('longitude')
            if not postcode or item_lat is None or item_lng is None:
                continue
            if not point_in_boundary(item_lat, item_lng, normalized):
                continue
            postcodes[postcode] = True
            outward = outward_code(postcode)
            if outward:
                districts.add(outward)
        if API_PAUSE_SECONDS:
            time.sleep(API_PAUSE_SECONDS)

    return {
        'postcode_count': len(postcodes),
        'district_count': len(districts),
        'sample_points': len(sample_points),
    }


def refresh_boundary_postcode_stats(row):
    stats = estimate_postcodes_in_ring(row.ring)
    row.estimated_postcode_count = stats['postcode_count']
    row.district_count = stats['district_count']
    row.save(update_fields=['estimated_postcode_count', 'district_count', 'updated_at'])
    return stats


def coverage_boundary_stats_summary(boundaries):
    total_postcodes = sum(int(item.get('estimated_postcode_count') or 0) for item in boundaries)
    total_districts = sum(int(item.get('district_count') or 0) for item in boundaries)
    return {
        'area_count': len(boundaries),
        'total_estimated_postcodes': total_postcodes,
        'total_districts': total_districts,
    }
