from app.models import JobOrder
from app.services.geo import haversine_m


def validate_clock_geofence(
    job: JobOrder,
    lat: float | None,
    lng: float | None,
) -> tuple[bool, float | None]:
    """Returns (is_valid, distance_m)."""
    if lat is None or lng is None:
        return False, None
    d = haversine_m(lat, lng, job.location_lat, job.location_lng)
    return d <= job.geofence_radius_m, d
