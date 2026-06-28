"""Geocoding and travel-time estimation for smart scheduling."""

import logging
import math
import re
from urllib.error import URLError
from urllib.parse import quote
from urllib.request import urlopen
import json

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

POSTCODE_RE = re.compile(r'^[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}$', re.IGNORECASE)


def normalize_postcode(postcode):
    if not postcode:
        return ''
    cleaned = re.sub(r'\s+', '', postcode.strip().upper())
    if len(cleaned) >= 5:
        return cleaned[:-3] + ' ' + cleaned[-3:]
    return cleaned


def is_valid_uk_postcode(postcode):
    return bool(POSTCODE_RE.match(normalize_postcode(postcode)))


def geocode_postcode(postcode):
    """Return (lat, lng) for a UK postcode via postcodes.io."""
    normalized = normalize_postcode(postcode)
    if not normalized:
        return None

    cache_key = f'geocode:{normalized.replace(" ", "")}'
    cached = cache.get(cache_key)
    if cached:
        return cached

    url = f'https://api.postcodes.io/postcodes/{quote(normalized.replace(" ", ""))}'
    try:
        with urlopen(url, timeout=5) as response:
            data = json.loads(response.read().decode())
        if data.get('status') != 200:
            return None
        result = data['result']
        coords = (float(result['latitude']), float(result['longitude']))
        cache.set(cache_key, coords, 60 * 60 * 24 * 30)
        return coords
    except (URLError, TimeoutError, KeyError, ValueError, json.JSONDecodeError) as exc:
        logger.warning('Geocoding failed for %s: %s', normalized, exc)
        return None


def haversine_km(lat1, lon1, lat2, lon2):
    radius = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def estimate_travel_minutes(origin, destination):
    """Estimate driving minutes using haversine + road factor."""
    if not origin or not destination:
        return getattr(settings, 'DEFAULT_TRAVEL_MINUTES', 30)

    lat1, lon1 = origin
    lat2, lon2 = destination
    if lat1 == lat2 and lon1 == lon2:
        return getattr(settings, 'MIN_TRAVEL_MINUTES', 5)

    distance_km = haversine_km(lat1, lon1, lat2, lon2)
    road_km = distance_km * getattr(settings, 'ROAD_DISTANCE_FACTOR', 1.35)
    speed_kmh = getattr(settings, 'AVERAGE_DRIVING_SPEED_KMH', 45)
    minutes = (road_km / speed_kmh) * 60
    buffer = getattr(settings, 'TRAVEL_BUFFER_MINUTES', 5)
    return max(
        getattr(settings, 'MIN_TRAVEL_MINUTES', 5),
        int(math.ceil(minutes + buffer)),
    )


def osrm_travel_minutes(origin, destination):
    """Driving minutes from OSRM; falls back to estimate on failure."""
    if not origin or not destination:
        return getattr(settings, 'DEFAULT_TRAVEL_MINUTES', 30)

    lat1, lon1 = origin
    lat2, lon2 = destination
    if lat1 == lat2 and lon1 == lon2:
        return getattr(settings, 'MIN_TRAVEL_MINUTES', 5)

    cache_key = f'travel:{lat1:.4f},{lon1:.4f}:{lat2:.4f},{lon2:.4f}'
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    base_url = getattr(
        settings,
        'OSRM_BASE_URL',
        'https://router.project-osrm.org/route/v1/driving',
    )
    url = f'{base_url}/{lon1},{lat1};{lon2},{lat2}?overview=false'
    try:
        with urlopen(url, timeout=6) as response:
            data = json.loads(response.read().decode())
        if data.get('code') == 'Ok' and data.get('routes'):
            seconds = data['routes'][0]['duration']
            minutes = max(
                getattr(settings, 'MIN_TRAVEL_MINUTES', 5),
                int(math.ceil(seconds / 60)) + getattr(settings, 'TRAVEL_BUFFER_MINUTES', 5),
            )
            cache.set(cache_key, minutes, 60 * 60 * 24 * 7)
            return minutes
    except (URLError, TimeoutError, KeyError, ValueError, json.JSONDecodeError) as exc:
        logger.warning('OSRM routing failed: %s', exc)

    minutes = estimate_travel_minutes(origin, destination)
    cache.set(cache_key, minutes, 60 * 60 * 24)
    return minutes


def travel_minutes(origin, destination):
    if getattr(settings, 'USE_OSRM_ROUTING', True):
        return osrm_travel_minutes(origin, destination)
    return estimate_travel_minutes(origin, destination)


def osrm_route_geometry(origin, destination):
    """Return GeoJSON-style [lon, lat] coordinates for map display."""
    if not origin or not destination:
        return []

    lat1, lon1 = origin
    lat2, lon2 = destination
    if lat1 == lat2 and lon1 == lon2:
        return [[lon1, lat1]]

    cache_key = f'routegeom:{lat1:.4f},{lon1:.4f}:{lat2:.4f},{lon2:.4f}'
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    base_url = getattr(
        settings,
        'OSRM_BASE_URL',
        'https://router.project-osrm.org/route/v1/driving',
    )
    url = f'{base_url}/{lon1},{lat1};{lon2},{lat2}?overview=full&geometries=geojson'
    try:
        with urlopen(url, timeout=8) as response:
            data = json.loads(response.read().decode())
        if data.get('code') == 'Ok' and data.get('routes'):
            geometry = data['routes'][0]['geometry']['coordinates']
            cache.set(cache_key, geometry, 60 * 60 * 24 * 7)
            return geometry
    except (URLError, TimeoutError, KeyError, ValueError, json.JSONDecodeError, OSError) as exc:
        logger.warning('OSRM geometry failed: %s', exc)

    geometry = [[lon1, lat1], [lon2, lat2]]
    cache.set(cache_key, geometry, 60 * 60 * 24)
    return geometry


def coords_for_address(postcode, city='', address_line_1=''):
    coords = geocode_postcode(postcode)
    if coords:
        return coords
    if city:
        return geocode_postcode(city)
    return None


def geocode_booking(booking):
    if booking.latitude is not None and booking.longitude is not None:
        return (float(booking.latitude), float(booking.longitude))
    return coords_for_address(booking.postcode, booking.city, booking.address_line_1)
