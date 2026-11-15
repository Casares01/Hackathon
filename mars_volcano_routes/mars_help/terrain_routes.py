"""Terrain routing over Mars Trek elevation grids. Coordinates are (lon, lat)."""
from __future__ import annotations
from dataclasses import dataclass
import heapq
import math
import numpy as np

MARS_RADIUS_M = 3_390_000.0

def normalize_lon(lon):
    return (float(lon) + 180.0) % 360.0 - 180.0


def distance_m(lon1, lat1, lon2, lat2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(normalize_lon(lon2 - lon1))
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * MARS_RADIUS_M * math.asin(min(1, math.sqrt(max(0, a))))


@dataclass(frozen=True)
class Waypoint:
    name: str
    lon: float
    lat: float


@dataclass
class TerrainRoute:
    coordinates: list[tuple[float, float]]
    visited: list[Waypoint]
    distance_m: float
    ascent_m: float
    descent_m: float
    maximum_slope_percent: float
    source: str = "MGS MOLA / NASA Mars Trek (approximate sampling)"


def plan_terrain_route(longitudes, latitudes, elevations, *, start_lon, start_lat,
                       waypoints, max_slope_percent=15.0, max_ascent_m=None):
    """Minimum-length feasible paths through the supplied stops in order.

    Uses 8-connected Dijkstra search with a local slope constraint. A global
    ascent limit is checked on the shortest legs; a longer low-ascent alternative
    is not searched, therefore failure is conservative rather than exhaustive.
    Stop positions are snapped to the nearest DEM cell; they are not verified
    accessible summit/landing coordinates.
    """
    xs, ys, z = map(lambda a: np.asarray(a, dtype=float),
                    (longitudes, latitudes, elevations))
    if xs.ndim != 1 or ys.ndim != 1 or z.shape != (len(ys), len(xs)):
        raise ValueError("Grid shape must be (len(latitudes), len(longitudes)).")
    if len(xs) < 2 or len(ys) < 2 or not np.all(np.diff(xs) > 0) or not np.all(np.diff(ys) > 0):
        raise ValueError("Latitude and longitude arrays must be sorted and contain at least two samples.")
    if not math.isfinite(max_slope_percent) or max_slope_percent < 0:
        raise ValueError("Invalid maximum slope.")
    if max_ascent_m is not None and max_ascent_m < 0:
        raise ValueError("Invalid ascent limit.")
    if len(waypoints) == 0:
        raise ValueError("Select at least one waypoint.")

    h, w = z.shape
    steps = [(di, dj) for di in (-1, 0, 1) for dj in (-1, 0, 1) if di or dj]

    def index_for(lon, lat, name):
        if not (xs[0] <= lon <= xs[-1] and ys[0] <= lat <= ys[-1]):
            raise ValueError(f"{name} is outside the downloaded region.")
        i, j = int(np.argmin(abs(ys - lat))), int(np.argmin(abs(xs - lon)))
        if not np.isfinite(z[i, j]):
            raise ValueError(f"No MOLA data at {name}.")
        return (i, j)

    indices = [index_for(normalize_lon(start_lon), start_lat, "Origin")]
    indices.extend(index_for(v.lon, v.lat, v.name) for v in waypoints)

    def shortest(src, dst):
        q = [(0.0, src)]
        dist = {src: 0.0}
        previous = {}
        while q:
            cost, (i, j) = heapq.heappop(q)
            if cost != dist[(i, j)]:
                continue
            if (i, j) == dst:
                result = [dst]
                while result[-1] != src:
                    result.append(previous[result[-1]])
                return result[::-1]
            for di, dj in steps:
                ni, nj = i + di, j + dj
                if not (0 <= ni < h and 0 <= nj < w) or not np.isfinite(z[ni, nj]):
                    continue
                # Avoid cutting a diagonal through a blocked/unknown orthogonal corner.
                if di and dj and (not np.isfinite(z[i, nj]) or not np.isfinite(z[ni, j])):
                    continue
                horizontal = distance_m(xs[j], ys[i], xs[nj], ys[ni])
                if horizontal < 1e-8:
                    continue
                dh = z[ni, nj] - z[i, j]
                slope = abs(dh) / horizontal * 100
                if slope > max_slope_percent:
                    continue
                new_cost = cost + math.hypot(horizontal, dh)
                if new_cost < dist.get((ni, nj), float("inf")):
                    dist[(ni, nj)] = new_cost
                    previous[(ni, nj)] = (i, j)
                    heapq.heappush(q, (new_cost, (ni, nj)))
        raise ValueError("No connection exists at this maximum slope on the MOLA grid.")

    nodes = []
    for n in range(len(indices) - 1):
        try:
            leg = shortest(indices[n], indices[n + 1])
        except ValueError as exc:
            raise ValueError(f"Cannot reach {waypoints[n].name}: {exc}") from exc
        nodes.extend(leg if n == 0 else leg[1:])
    length = up = down = maxslope = 0.0
    for (i, j), (ni, nj) in zip(nodes, nodes[1:]):
        horizontal = distance_m(xs[j], ys[i], xs[nj], ys[ni])
        dh = z[ni, nj] - z[i, j]
        length += math.hypot(horizontal, dh)
        up += max(0.0, dh)
        down += max(0.0, -dh)
        maxslope = max(maxslope, abs(dh) / horizontal * 100)
    if max_ascent_m is not None and up > max_ascent_m:
        raise ValueError(f"The shortest route exceeds the ascent limit: {up:.0f} m > {max_ascent_m:.0f} m. "
                         "A longer alternative may exist; it was not searched.")
    coordinates = [(float(xs[j]), float(ys[i])) for i, j in nodes]
    return TerrainRoute(coordinates, list(waypoints), length, up, down, maxslope)
