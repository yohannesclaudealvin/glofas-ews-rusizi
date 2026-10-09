"""Station maps: river geometry from OpenStreetMap (Overpass API) + Folium map.

The map shows the gauging station, the GloFAS 0.05° cell used for the forecast,
and the river traced from OpenStreetMap. It can be downloaded as a standalone
HTML file (interactive) and the geometry as GeoJSON.
"""
from __future__ import annotations

import difflib
import html as _html
import json
import unicodedata

import folium
import requests
from folium.plugins import Fullscreen, MeasureControl, MiniMap

OVERPASS = ["https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter"]
HEADERS = {"User-Agent": "glofas-ews-rusizi/1.0 (flood early warning, Burundi)"}

# names used in OpenStreetMap when they differ from the IGEBU station name
ALIASES = {"RUSIZI": ["Rusizi", "Ruzizi"], "KAGUNUZI": ["Kagunuzi", "Kagunizi"]}


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    return s.replace("riviere", "").replace("river", "").strip()


def fetch_rivers(lat: float, lon: float, radius_m: int = 30000, timeout: int = 40) -> list[dict]:
    """All named rivers/streams around a point: [{'name', 'coords': [[lat, lon], ...]}, ...]."""
    q = (f'[out:json][timeout:{timeout}];(way["waterway"~"river|stream"]["name"](around:{radius_m},{lat},{lon}););'
         'out geom;')
    last = None
    for url in OVERPASS:
        try:
            r = requests.post(url, data={"data": q}, headers=HEADERS, timeout=timeout + 10)
            r.raise_for_status()
            out = []
            for e in r.json().get("elements", []):
                if e.get("geometry"):
                    out.append({"name": _html.escape(e.get("tags", {}).get("name", "")),
                                "waterway": e.get("tags", {}).get("waterway", ""),
                                "coords": [[p["lat"], p["lon"]] for p in e["geometry"]]})
            return out
        except Exception as ex:   # try the next mirror
            last = ex
    raise RuntimeError(f"OpenStreetMap (Overpass) indisponible : {last}")


BURUNDI = (-4.50, 28.95, -2.28, 30.90)      # south, west, north, east


def search_river(name: str, bbox=BURUNDI, timeout: int = 60) -> list[dict]:
    """Ways of the river called `name` (any spelling case) inside `bbox` (Burundi by default)."""
    s, w, n, e = bbox
    safe = "".join(ch for ch in name.strip() if ch.isalnum() or ch in " -'")
    q = (f'[out:json][timeout:{timeout}];way["waterway"~"river|stream"]["name"~"^{safe}$",i]'
         f'({s},{w},{n},{e});out geom;')
    last = None
    for url in OVERPASS:
        try:
            r = requests.post(url, data={"data": q}, headers=HEADERS, timeout=timeout + 10)
            r.raise_for_status()
            return [{"name": _html.escape(el.get("tags", {}).get("name", "")),
                     "waterway": el.get("tags", {}).get("waterway", ""),
                     "coords": [[p["lat"], p["lon"]] for p in el["geometry"]]}
                    for el in r.json().get("elements", []) if el.get("geometry")]
        except Exception as ex:
            last = ex
    raise RuntimeError(f"OpenStreetMap (Overpass) indisponible : {last}")


def _km(a, b):
    import math
    k = math.pi / 180
    return 6371 * math.hypot((b[1] - a[1]) * k * math.cos((a[0] + b[0]) / 2 * k), (b[0] - a[0]) * k)


def propose_point(ways: list[dict], upstream_km: float = 3.0):
    """A plausible gauge position: `upstream_km` above the river outlet.

    OpenStreetMap draws waterways in the direction of flow, so the outlet is the last node of the
    way whose end is not the start of another way of the same river. Returns (lat, lon, outlet).
    """
    if not ways:
        return None
    starts = {tuple(w["coords"][0]) for w in ways}
    ends = [w for w in ways if tuple(w["coords"][-1]) not in starts] or ways
    # several candidate outlets (tributaries with the same name): keep the longest chain's one
    w = max(ends, key=lambda w: len(w["coords"]))
    pts = w["coords"][::-1]
    acc, p = 0.0, pts[0]
    for a, b in zip(pts[:-1], pts[1:]):
        acc += _km(a, b)
        p = b
        if acc >= upstream_km:
            break
    return round(p[0], 4), round(p[1], 4), (round(pts[0][0], 4), round(pts[0][1], 4))


def match_river(ways: list[dict], river_name: str, station: str | None = None) -> tuple[str | None, list[dict]]:
    """Ways of the station's river: exact (accent-insensitive) names first, then partial, then fuzzy."""
    targets = {_norm(t) for t in [river_name] + ALIASES.get((station or "").upper(), []) if t}
    names = sorted({w["name"] for w in ways})
    exact = [n for n in names if _norm(n) in targets]
    if exact:
        return " / ".join(exact), [w for w in ways if w["name"] in exact]
    scored = []
    for n in names:
        for t in targets:
            if t and (t in _norm(n).split() or _norm(n).startswith(t)):
                scored.append((0.9, n))
            else:
                scored.append((difflib.SequenceMatcher(None, _norm(n), t).ratio(), n))
    if not scored:
        return None, []
    score, best = max(scored)
    if score < 0.8:
        return None, []
    return best, [w for w in ways if w["name"] == best]


def station_map(station: str, river: str, lat: float, lon: float, cell_lat: float | None = None,
                cell_lon: float | None = None, river_ways: list[dict] | None = None,
                other_ways: list[dict] | None = None, others: list[dict] | None = None) -> folium.Map:
    m = folium.Map(location=[lat, lon], zoom_start=11, tiles=None, control_scale=True)
    folium.TileLayer("OpenStreetMap", name="OpenStreetMap").add_to(m)
    folium.TileLayer("https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png", attr="© OpenTopoMap (CC-BY-SA)",
                     name="Relief (OpenTopoMap)", show=False).add_to(m)
    folium.TileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
                     attr="Esri, Maxar, Earthstar Geographics", name="Satellite (Esri)", show=False).add_to(m)

    if other_ways:
        g = folium.FeatureGroup(name="Autres cours d'eau", show=True)
        for w in other_ways:
            folium.PolyLine(w["coords"], color="#86b6ef", weight=1.5, opacity=0.8, tooltip=w["name"]).add_to(g)
        g.add_to(m)
    if river_ways:
        g = folium.FeatureGroup(name=f"Rivière {river}", show=True)
        for w in river_ways:
            folium.PolyLine(w["coords"], color="#1c5cab", weight=4, opacity=0.95, tooltip=w["name"]).add_to(g)
        g.add_to(m)
    if cell_lat is not None and cell_lon is not None:
        h = 0.025
        folium.Rectangle([[cell_lat - h, cell_lon - h], [cell_lat + h, cell_lon + h]], color="#eb6834", weight=2,
                         fill=True, fill_opacity=0.08,
                         tooltip=f"Maille GloFAS 0,05° ({cell_lat:.3f}, {cell_lon:.3f})").add_to(m)
    for o in others or []:
        folium.CircleMarker([o["lat"], o["lon"]], radius=5, color="#6b7280", fill=True, fill_opacity=0.8,
                            tooltip=f"{o['station']} ({o.get('river', '')})").add_to(m)
    folium.Marker([lat, lon], tooltip=f"<b>{station}</b><br>Rivière : {river}<br>{lat:.4f}, {lon:.4f}",
                  popup=folium.Popup(f"<b>Station {station}</b><br>Rivière : {river}<br>Lat : {lat:.5f}<br>"
                                     f"Lon : {lon:.5f}", max_width=250),
                  icon=folium.Icon(color="darkblue", icon="tint", prefix="fa")).add_to(m)
    Fullscreen().add_to(m)
    MeasureControl(primary_length_unit="kilometers").add_to(m)
    MiniMap(toggle_display=True, position="bottomleft").add_to(m)
    folium.LayerControl(collapsed=False).add_to(m)
    bounds = [[lat, lon]]
    for w in river_ways or []:
        bounds += w["coords"]
    if len(bounds) > 1:
        la = [b[0] for b in bounds]; lo = [b[1] for b in bounds]
        # keep the view centred on the station, at most ~40 km around it
        m.fit_bounds([[max(min(la), lat - 0.35), max(min(lo), lon - 0.35)],
                      [min(max(la), lat + 0.35), min(max(lo), lon + 0.35)]])
    return m


def map_html(m: folium.Map) -> str:
    return m.get_root().render()


def geojson(station: str, river: str, lat: float, lon: float, cell_lat=None, cell_lon=None, river_ways=None) -> str:
    feats = [{"type": "Feature", "properties": {"type": "station", "station": station, "river": river},
              "geometry": {"type": "Point", "coordinates": [lon, lat]}}]
    if cell_lat is not None and cell_lon is not None:
        h = 0.025
        ring = [[cell_lon - h, cell_lat - h], [cell_lon + h, cell_lat - h], [cell_lon + h, cell_lat + h],
                [cell_lon - h, cell_lat + h], [cell_lon - h, cell_lat - h]]
        feats.append({"type": "Feature", "properties": {"type": "glofas_cell", "station": station},
                      "geometry": {"type": "Polygon", "coordinates": [ring]}})
    for w in river_ways or []:
        feats.append({"type": "Feature", "properties": {"type": "river", "name": w["name"]},
                      "geometry": {"type": "LineString", "coordinates": [[c[1], c[0]] for c in w["coords"]]}})
    return json.dumps({"type": "FeatureCollection", "features": feats}, ensure_ascii=False)
