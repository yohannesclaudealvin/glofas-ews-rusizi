"""Access to GloFAS v4 through the Open-Meteo Flood API.

https://open-meteo.com/en/docs/flood-api  - free, no key, 0.05 deg grid.
`river_discharge` is the deterministic GloFAS value; the ensemble statistics
(min, p25, median, p75, max) describe the spread of the 51-member forecast.
"""
from __future__ import annotations

import time

import numpy as np
import pandas as pd
import requests

URL = "https://flood-api.open-meteo.com/v1/flood"
ENSEMBLE_VARS = ["river_discharge", "river_discharge_mean", "river_discharge_median", "river_discharge_min",
                 "river_discharge_max", "river_discharge_p25", "river_discharge_p75"]


def _get(params: dict, retries: int = 3) -> dict | list:
    for i in range(retries):
        r = requests.get(URL, params=params, timeout=60)
        if r.status_code == 429 or (r.ok and isinstance(r.json(), dict) and r.json().get("error")
                                    and "limit" in str(r.json().get("reason", "")).lower()):
            time.sleep(61)          # per-minute limit of the free API
            continue
        r.raise_for_status()
        js = r.json()
        if isinstance(js, dict) and js.get("error"):
            raise RuntimeError(js.get("reason"))
        return js
    raise RuntimeError("Open-Meteo request limit reached, try again in a minute")


def _to_df(js: dict) -> pd.DataFrame:
    d = pd.DataFrame(js["daily"])
    d["time"] = pd.to_datetime(d["time"])
    return d.set_index("time")


def fetch_forecast(lat: float, lon: float, past_days: int = 7, forecast_days: int = 8,
                   ensemble: bool = True) -> pd.DataFrame:
    """Latest GloFAS forecast (today and the next `forecast_days - 1` days) + recent past."""
    params = {"latitude": lat, "longitude": lon,
              "daily": ",".join(ENSEMBLE_VARS if ensemble else ENSEMBLE_VARS[:1]),
              "past_days": past_days, "forecast_days": forecast_days}
    return _to_df(_get(params))


def fetch_history(lat: float, lon: float, start: str, end: str) -> pd.DataFrame:
    params = {"latitude": lat, "longitude": lon, "daily": "river_discharge", "start_date": start, "end_date": end}
    return _to_df(_get(params))


def find_cell(lat: float, lon: float, reference: pd.Series, radius: int = 3, step: float = 0.05,
              start: str | None = None, end: str | None = None) -> pd.DataFrame:
    """Rank the GloFAS cells around (lat, lon) by similarity with a reference series.

    reference: a discharge series for the station (e.g. the 1-day GloFAS forecast
    file used in the analysis, or observations). Cells are scored by the
    correlation of monthly means and the ratio of mean discharge.
    """
    ref = reference.dropna()
    if start is None:
        end_d = min(ref.index.max(), pd.Timestamp("2023-12-31"))
        start_d = max(ref.index.min(), end_d - pd.DateOffset(years=4))
        start, end = start_d.strftime("%Y-%m-%d"), end_d.strftime("%Y-%m-%d")
    lats, lons = [], []
    for i in range(-radius, radius + 1):
        for j in range(-radius, radius + 1):
            lats.append(round(lat + i * step, 3)); lons.append(round(lon + j * step, 3))
    js = _get({"latitude": ",".join(map(str, lats)), "longitude": ",".join(map(str, lons)),
               "daily": "river_discharge", "start_date": start, "end_date": end})
    js = js if isinstance(js, list) else [js]
    refm = ref.loc[start:end].resample("MS").mean()
    rows = []
    for p in js:
        s = _to_df(p)["river_discharge"]
        if s.mean() < 0.05:
            continue
        sm = s.resample("MS").mean()
        both = pd.concat([sm, refm], axis=1).dropna()
        r = both.corr().iloc[0, 1] if len(both) > 3 else np.nan
        rows.append({"cell_lat": round(p["latitude"], 3), "cell_lon": round(p["longitude"], 3),
                     "glofas_mean": s.mean(), "ref_mean": refm.mean(),
                     "mean_ratio": s.mean() / refm.mean(), "corr_monthly": r})
    df = pd.DataFrame(rows).drop_duplicates(["cell_lat", "cell_lon"])
    df["score"] = df["corr_monthly"].fillna(0) - np.abs(np.log(df["mean_ratio"]))
    return df.sort_values("score", ascending=False).reset_index(drop=True)
