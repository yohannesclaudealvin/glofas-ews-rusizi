"""GloFAS forecasts from Copernicus (CEMS Early Warning Data Store): download and point extraction.

Second download route, as in the original IGEBU interface: the user gives his Copernicus API key,
the limits of the zone and the forecast date; the app downloads the official GloFAS forecast
(control + 50 perturbed members, up to 30 days) and extracts the series at the station's cell.

The request follows the one used in the AGRHYMET GloFAS toolkit (dataset ``cems-glofas-forecast``,
system_version ``operational``, model ``lisflood``, variable ``river_discharge_in_the_last_24_hours``,
one request per product type, daily lead times 24 h ... N×24 h). NetCDF is asked first; if the
catalogue refuses it, GRIB2 is used (read with cfgrib/ecCodes). Files may come zipped.

Dataset page: https://ewds.climate.copernicus.eu/datasets/cems-glofas-forecast
(an account and the acceptance of the dataset licence are needed once).
"""
from __future__ import annotations

import io
import os
import socket
import tempfile
import zipfile
from urllib.parse import urlparse

import numpy as np
import pandas as pd

from .snap import snap_on_grid

EWDS_URL = "https://ewds.climate.copernicus.eu/api"
DATASET = "cems-glofas-forecast"
PRODUCTS = {"control": "control_forecast", "perturbed": "ensemble_perturbed_forecasts"}
BURUNDI_BBOX = {"lat_max": -2.25, "lat_min": -4.50, "lon_min": 28.95, "lon_max": 30.90}
# download zones ("watershed" button of the original interface)
ZONES = {
    "Burundi entier": BURUNDI_BBOX,
    "Bassin de la Rusizi (Burundi)": {"lat_max": -2.55, "lat_min": -3.60, "lon_min": 28.95, "lon_max": 29.80},
    "Affluents du lac Tanganyika (sud)": {"lat_max": -3.30, "lat_min": -4.50, "lon_min": 29.20, "lon_max": 29.95},
}


# ----------------------------------------------------------------------------------------- key / network
def configured_key(secrets=None) -> str | None:
    """Copernicus key configured once 'in the system': Streamlit secrets, environment or ~/.cdsapirc."""
    try:
        if secrets is not None and secrets.get("CDS_API_KEY"):
            return str(secrets["CDS_API_KEY"])
    except Exception:
        pass
    for v in ("CDSAPI_KEY", "CDS_API_KEY"):
        if os.environ.get(v):
            return os.environ[v]
    for rc in (os.environ.get("CDSAPI_RC"), os.path.expanduser("~/.cdsapirc-ewds"), os.path.expanduser("~/.cdsapirc")):
        if rc and os.path.exists(rc):
            for line in open(rc, encoding="utf-8"):
                if line.strip().startswith("key:"):
                    return line.split(":", 1)[1].strip()
    return None


def check_network(url: str = EWDS_URL, timeout: float = 8.0):
    """Fail fast when the EWDS cannot be reached (cdsapi would otherwise retry for hours)."""
    host = urlparse(url).hostname or url
    try:
        socket.create_connection((host, 443), timeout=timeout).close()
    except OSError as exc:
        raise RuntimeError(f"impossible de joindre {host} ({exc}) : vérifiez la connexion internet, "
                           "ou un pare-feu/proxy qui bloquerait ce site") from exc


def _client(key: str, url: str):
    import cdsapi
    try:
        return cdsapi.Client(url=url, key=key.strip(), quiet=True, progress=False, retry_max=3, sleep_max=10,
                             timeout=300)
    except TypeError:          # older/newer cdsapi without some of these options
        return cdsapi.Client(url=url, key=key.strip(), quiet=True, progress=False)


def grib_available() -> bool:
    try:
        import cfgrib  # noqa: F401
        return True
    except Exception:
        return False


# ----------------------------------------------------------------------------------------- download
def build_request(day, bbox: dict, days: int, product: str, data_format: str) -> dict:
    day = pd.Timestamp(day)
    return {
        "system_version": ["operational"],
        "hydrological_model": ["lisflood"],
        "product_type": [product],
        "variable": "river_discharge_in_the_last_24_hours",
        "year": [f"{day.year}"], "month": [f"{day.month:02d}"], "day": [f"{day.day:02d}"],
        "leadtime_hour": [str(24 * h) for h in range(1, days + 1)],
        "data_format": data_format,
        "download_format": "zip",
        "area": [bbox["lat_max"], bbox["lon_min"], bbox["lat_min"], bbox["lon_max"]],   # N, W, S, E
    }


def download_forecast(key: str, day, bbox: dict, days: int = 30, ensemble: bool = True, url: str = EWDS_URL,
                      log=None) -> dict:
    """Download the GloFAS forecast issued on `day` for the zone `bbox`.

    Returns {"control": bytes, "perturbed": bytes} (zip/NetCDF/GRIB content, as received).
    """
    log = log or (lambda m: None)
    check_network(url)
    client = _client(key, url)
    formats = ["netcdf"] + (["grib2"] if grib_available() else [])
    out = {}
    for short in (["control", "perturbed"] if ensemble else ["control"]):
        last = None
        for fmt in formats:
            req = build_request(day, bbox, max(1, min(int(days), 30)), PRODUCTS[short], fmt)
            try:
                log(f"Requête EWDS {short} ({fmt}, {len(req['leadtime_hour'])} échéances)…")
                with tempfile.TemporaryDirectory() as d:
                    target = os.path.join(d, f"glofas_{short}.zip")
                    client.retrieve(DATASET, req, target)
                    with open(target, "rb") as f:
                        data = f.read()
                if not data:
                    raise RuntimeError("fichier reçu vide")
                out[short] = data
                break
            except Exception as e:
                last = e
                msg = str(e).lower()
                if not any(k in msg for k in ("format", "netcdf", "not available", "invalid")):
                    break            # licence, key, network... : no point trying another format
        if short not in out:
            if short == "perturbed" and "control" in out:
                log(f"Membres perturbés indisponibles ({last}) : seul le contrôle sera utilisé")
                continue
            raise last
    return out


# ----------------------------------------------------------------------------------------- reading
def _members(data) -> list[bytes]:
    """Raw files from bytes / zip / dict / list of them."""
    if isinstance(data, dict):
        data = list(data.values())
    if isinstance(data, (list, tuple)):
        return [m for d in data for m in _members(d)]
    if data[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            return [z.read(n) for n in z.namelist() if not n.endswith("/")]
    return [data]


def unzip_nc(data: bytes) -> bytes:
    """First data file of a (possibly zipped) download."""
    return _members(data)[0]


def _open_one(raw: bytes):
    import xarray as xr
    if raw[:4] == b"GRIB":
        if not grib_available():
            raise ValueError("fichier GRIB : installez cfgrib et eccodes pour le lire")
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "f.grib")
            with open(p, "wb") as f:
                f.write(raw)
            return xr.open_dataset(p, engine="cfgrib", backend_kwargs={"indexpath": ""}).load()
    for engine in ("h5netcdf", "netcdf4", "scipy"):
        try:
            return xr.open_dataset(io.BytesIO(raw), engine=engine).load()
        except Exception:
            continue
    raise ValueError("fichier GloFAS illisible (ni NetCDF ni GRIB)")


def _open(data):
    return _open_one(_members(data)[0])


def _name(ds, *cands):
    for c in cands:
        if c in ds.dims or c in ds.coords:
            return c
    return None


def _standard(ds):
    """DataArray (time, member, lat, lon) + valid dates (day covered by each 24-h mean)."""
    var = next((v for v in ("dis24", "dis06", "dis") if v in ds.data_vars),
               next(v for v in ds.data_vars if ds[v].ndim >= 2))
    da = ds[var]
    la, lo = _name(da, "latitude", "lat"), _name(da, "longitude", "lon")
    da = da.rename({la: "lat", lo: "lon"})
    step = _name(da, "step", "leadtime")
    ref = _name(da, "forecast_reference_time", "time")
    if "valid_time" in da.coords and da["valid_time"].ndim == 1 and da["valid_time"].dims[0] in da.dims:
        tdim = da["valid_time"].dims[0]
        vt = pd.to_datetime(da["valid_time"].values)
    elif step is not None and step in da.dims:
        r = pd.Timestamp(np.asarray(da[ref].values).ravel()[0]) if ref is not None else pd.Timestamp(0)
        tdim, vt = step, r + pd.to_timedelta(da[step].values)
    else:
        tdim, vt = ref, pd.to_datetime(da[ref].values)
    for d in list(da.dims):
        if d not in (tdim, "number", "lat", "lon") and da.sizes[d] == 1:
            da = da.isel({d: 0})
    if "number" not in da.dims:
        n = int(np.asarray(da["number"].values).ravel()[0]) if "number" in da.coords else 0
        da = da.drop_vars("number", errors="ignore").expand_dims(number=[n])
    da = da.transpose(tdim, "number", "lat", "lon")
    dates = pd.DatetimeIndex(vt).normalize() - pd.Timedelta(days=1)
    return da, dates


def extract_point(data, lat: float, lon: float, radius_km: float = 0.0) -> pd.DataFrame:
    """GloFAS series at the station cell, in the same format as the Open-Meteo route.

    data: one download (bytes, zip) or several (dict/list: control + perturbed).
    radius_km > 0: the station is snapped onto the cell of largest mean discharge within the radius.
    Columns: river_discharge (control, or ensemble mean without control), ensemble statistics
    (_min, _p25, _median, _p75, _max, _mean) and members river_discharge_member01..50.
    attrs: cell, status, distance_km.
    """
    parts = [_standard(_open_one(raw)) for raw in _members(data)]
    da0 = parts[0][0]
    lats, lons = da0["lat"].values, da0["lon"].values
    stat = da0.mean(dim=[da0.dims[0], "number"]).values if radius_km > 0 else None
    snap = snap_on_grid(lats, lons, stat, lat, lon, radius_km)
    series = {}
    for da, dates in parts:
        pt = da.sel(lat=snap["lat"], lon=snap["lon"], method="nearest")
        for k, n in enumerate(pt["number"].values):
            s = pd.Series(pt.isel(number=k).values.astype(float), index=dates)
            series[int(n)] = s[~s.index.duplicated()]
    mat = pd.DataFrame(series).sort_index()
    out = pd.DataFrame(index=mat.index)
    members = [c for c in mat.columns if c != 0]
    out["river_discharge"] = mat[0] if 0 in mat.columns else mat.mean(axis=1)
    if mat.shape[1] > 1:
        arr = mat.values
        out["river_discharge_mean"] = np.nanmean(arr, axis=1)
        out["river_discharge_min"] = np.nanmin(arr, axis=1)
        out["river_discharge_p25"] = np.nanpercentile(arr, 25, axis=1)
        out["river_discharge_median"] = np.nanmedian(arr, axis=1)
        out["river_discharge_p75"] = np.nanpercentile(arr, 75, axis=1)
        out["river_discharge_max"] = np.nanmax(arr, axis=1)
        for c in members:
            out[f"river_discharge_member{c:02d}"] = mat[c]
    out.attrs.update(cell=(snap["lat"], snap["lon"]), status=snap["status"], distance_km=snap["distance_km"])
    return out
