"""Snap a station onto the GloFAS river network.

A station's coordinates rarely fall exactly on the river channel simulated by GloFAS (0.05° grid):
the nearest cell can belong to a hillslope with almost no flow, or to a neighbouring catchment.
As in the AGRHYMET GloFAS toolkit, we look at every cell within `radius_km` of the station and keep
the one with the largest mean discharge, i.e. the cell most likely to be on the channel.

Status of the result:
* "ok"      : the nearest cell was kept;
* "recalé"  : another cell inside the radius has a larger discharge and was chosen;
* "repli"   : no valid cell inside the radius, fallback to the nearest cell.
"""
from __future__ import annotations

import math

import numpy as np

EARTH_RADIUS_KM = 6371.0088


def haversine_km(lat1, lon1, lat2, lon2):
    lat1, lon1 = math.radians(lat1), math.radians(lon1)
    lat2, lon2 = np.radians(lat2), np.radians(lon2)
    a = np.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return 2 * EARTH_RADIUS_KM * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


def snap_on_grid(lats: np.ndarray, lons: np.ndarray, stat: np.ndarray | None, lat0: float, lon0: float,
                 radius_km: float = 0.0):
    """Choose a cell of the regular grid (lats, lons) for the point (lat0, lon0).

    stat: 2-D array (lat, lon) of mean discharge, used when radius_km > 0.
    Returns dict(i, j, lat, lon, distance_km, status).
    """
    lats, lons = np.asarray(lats, float), np.asarray(lons, float)
    i0, j0 = int(np.abs(lats - lat0).argmin()), int(np.abs(lons - lon0).argmin())

    def res(i, j, status):
        d = float(haversine_km(lat0, lon0, np.array([lats[i]]), np.array([lons[j]]))[0])
        return dict(i=int(i), j=int(j), lat=float(lats[i]), lon=float(lons[j]), distance_km=round(d, 2),
                    status=status)

    if radius_km <= 0 or stat is None:
        return res(i0, j0, "ok")
    LO, LA = np.meshgrid(lons, lats)
    dist = haversine_km(lat0, lon0, LA.ravel(), LO.ravel()).reshape(LA.shape)
    st = np.where((dist <= radius_km) & np.isfinite(stat), stat, -np.inf)
    if not np.isfinite(st).any() or st.max() <= 0:
        return res(i0, j0, "repli")
    i, j = np.unravel_index(int(np.argmax(st)), st.shape)
    return res(i, j, "ok" if (i, j) == (i0, j0) else "recalé")


def candidate_cells(lat0: float, lon0: float, radius_km: float, step: float = 0.05):
    """Centres of the GloFAS 0.05° cells (x.x25 / x.x75) within radius_km of the point."""
    half = step / 2
    c_lat = math.floor((lat0 - half) / step) * step + half
    c_lon = math.floor((lon0 - half) / step) * step + half
    n = int(math.ceil(radius_km / 5.5)) + 1
    out = []
    for i in range(-n, n + 2):
        for j in range(-n, n + 2):
            la, lo = round(c_lat + i * step, 3), round(c_lon + j * step, 3)
            if float(haversine_km(lat0, lon0, np.array([la]), np.array([lo]))[0]) <= max(radius_km, 3.6):
                out.append((la, lo))
    return out
