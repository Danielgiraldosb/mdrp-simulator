"""
Planar Euclidean distance + travel time, matching mdrplib's own evaluator
exactly (see MDRP_code/compute_performance_summary.py::traveltime):

    tt = ceil( sqrt((x2-x1)^2 + (y2-y1)^2) / meters_per_minute )

mdrplib gives ONE meters_per_minute value per instance -- there is no
per-vehicle speed table. Travel time therefore depends only on the
instance's own speed parameter, which is exactly the lever the 't100'/'t75'
design factor varies. (A previous lat/lon + Haversine + per-vehicle-speed
adaptation of this simulator ignored that parameter entirely, silently
erasing the t100/t75 factor -- this module is the fix.)
"""
from __future__ import annotations
import math

from models import Location


def dist_m(a: Location, b: Location) -> float:
    """Euclidean distance in meters."""
    return math.hypot(b.x - a.x, b.y - a.y)


def dist_km(a: Location, b: Location) -> float:
    """Euclidean distance in km."""
    return dist_m(a, b) / 1000.0


def travel_time_min(a: Location, b: Location, meters_per_minute: float) -> float:
    """Travel time in minutes, rounded up -- identical formula to the official evaluator."""
    if meters_per_minute <= 0:
        return 0.0
    return math.ceil(dist_m(a, b) / meters_per_minute)
