from math import atan2, cos, radians, sin, sqrt

EARTH_RADIUS_M = 6371000.0


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in meters."""
    r1, r2 = radians(lat1), radians(lat2)
    dphi = radians(lat2 - lat1)
    dlmb = radians(lon2 - lon1)
    a = sin(dphi / 2) ** 2 + cos(r1) * cos(r2) * sin(dlmb / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return EARTH_RADIUS_M * c


def within_radius(
    worker_lat: float | None,
    worker_lng: float | None,
    site_lat: float,
    site_lng: float,
    radius_m: float,
) -> bool:
    if worker_lat is None or worker_lng is None:
        return False
    return haversine_m(worker_lat, worker_lng, site_lat, site_lng) <= radius_m
