"""GloFAS forecasts from Copernicus (CEMS Early Warning Data Store) as NetCDF.

Second download route, as in the original IGEBU interface: the user gives his
Copernicus API key, the geographic limits of the zone and the forecast date;
the app downloads the NetCDF file of the GloFAS forecast (control + 50-member
ensemble) and extracts the series at the station's grid cell.

Dataset: ``cems-glofas-forecast`` on https://ewds.climate.copernicus.eu
(an account and the acceptance of the dataset licence are needed once).
"""
from __future__ import annotations

import io
import os
import tempfile

import numpy as np
import pandas as pd

EWDS_URL = "https://ewds.climate.copernicus.eu/api"
DATASET = "cems-glofas-forecast"
BURUNDI_BBOX = {"lat_max": -2.25, "lat_min": -4.50, "lon_min": 28.95, "lon_max": 30.90}


def download_forecast(key: str, day, bbox: dict, days: int = 7, ensemble: bool = True,
                      url: str = EWDS_URL) -> bytes:
    """Download the GloFAS forecast issued on `day` for the zone `bbox`; returns NetCDF bytes."""
    import cdsapi  # imported here so the app works without it when this route is not used

    day = pd.Timestamp(day)
    req = {
        "system_version": ["operational"],
        "hydrological_model": ["lisflood"],
        "product_type": ["control_forecast", "ensemble_perturbed_forecasts"] if ensemble else ["control_forecast"],
        "variable": "river_discharge_in_the_last_24_hours",
        "year": [f"{day.year}"], "month": [f"{day.month:02d}"], "day": [f"{day.day:02d}"],
        "leadtime_hour": [str(24 * h) for h in range(1, days + 2)],
        "data_format": "netcdf",
        "download_format": "unarchived",
        "area": [bbox["lat_max"], bbox["lon_min"], bbox["lat_min"], bbox["lon_max"]],   # N, W, S, E
    }
    client = cdsapi.Client(url=url, key=key.strip(), quiet=True, progress=False)
    with tempfile.TemporaryDirectory() as d:
        target = os.path.join(d, "glofas.nc")
        client.retrieve(DATASET, req, target)
        with open(target, "rb") as f:
            return f.read()


def _open(nc: bytes):
    import xarray as xr
    for engine in ("h5netcdf", "netcdf4", "scipy"):
        try:
            return xr.open_dataset(io.BytesIO(nc), engine=engine).load()
        except Exception:
            continue
    raise ValueError("Fichier NetCDF illisible (format non reconnu).")


def _name(ds, *cands):
    for c in cands:
        if c in ds.dims or c in ds.coords:
            return c
    return None


def extract_point(nc: bytes, lat: float, lon: float) -> pd.DataFrame:
    """GloFAS series at the cell nearest to (lat, lon), in the same format as the Open-Meteo route.

    Columns: river_discharge (control, or ensemble mean if no control) and, when ensemble
    members exist, river_discharge_min / _p25 / _median / _p75 / _max / _mean.
    Each 24-h mean is dated with the day it covers (valid time minus 24 h).
    """
    ds = _open(nc)
    var = next((v for v in ("dis24", "dis06", "dis") if v in ds.data_vars), list(ds.data_vars)[0])
    da = ds[var]
    la, lo = _name(ds, "latitude", "lat"), _name(ds, "longitude", "lon")
    pt = da.sel({la: lat, lo: lon}, method="nearest")
    cell = (float(pt[la]), float(pt[lo]))

    # time axis: valid_time if given, else reference time + step
    step = _name(pt, "step", "leadtime")
    ref = _name(pt, "forecast_reference_time", "time")
    if "valid_time" in pt.coords and pt["valid_time"].ndim == 1:
        vt = pd.to_datetime(pt["valid_time"].values)
        tdim = pt["valid_time"].dims[0]
    elif step is not None:
        r = pd.Timestamp(pt[ref].values.ravel()[0]) if ref is not None else None
        stp = pd.to_timedelta(pt[step].values)
        vt = (r + stp) if r is not None else pd.to_datetime(stp)
        tdim = step
    else:
        vt = pd.to_datetime(pt[ref].values); tdim = ref
    for d in list(pt.dims):                       # drop singleton reference-time dims
        if d not in (tdim, "number") and pt.sizes[d] == 1:
            pt = pt.isel({d: 0})
    dates = pd.DatetimeIndex(vt).normalize() - pd.Timedelta(days=1)

    out = pd.DataFrame(index=dates)
    if "number" in pt.dims and pt.sizes["number"] > 1:
        arr = pt.transpose(tdim, "number").values.astype(float)       # (time, member)
        nums = pt["number"].values
        ctrl = arr[:, list(nums).index(0)] if 0 in nums else np.nanmean(arr, axis=1)
        out["river_discharge"] = ctrl
        out["river_discharge_mean"] = np.nanmean(arr, axis=1)
        out["river_discharge_min"] = np.nanmin(arr, axis=1)
        out["river_discharge_p25"] = np.nanpercentile(arr, 25, axis=1)
        out["river_discharge_median"] = np.nanmedian(arr, axis=1)
        out["river_discharge_p75"] = np.nanpercentile(arr, 75, axis=1)
        out["river_discharge_max"] = np.nanmax(arr, axis=1)
    else:
        if "number" in pt.dims:
            pt = pt.isel(number=0)
        out["river_discharge"] = pt.values.astype(float).ravel()
    out = out[~out.index.duplicated()].sort_index()
    out.attrs["cell"] = cell
    return out
