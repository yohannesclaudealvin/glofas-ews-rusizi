"""Reading observation and GloFAS files (Excel or CSV), and quality control."""
from __future__ import annotations

import io
import re
from pathlib import Path

import numpy as np
import pandas as pd

from . import LT_COLS


def _read_any(src, name: str | None = None) -> pd.DataFrame:
    """Read an Excel/CSV file given a path, bytes or an uploaded-file object."""
    name = name or getattr(src, "name", None) or str(src)
    if isinstance(src, (bytes, bytearray)):
        src = io.BytesIO(src)
    if str(name).lower().endswith(".csv"):
        return pd.read_csv(src)
    return pd.read_excel(src)


def _clean_station(s: str) -> str:
    s = re.sub(r"(?i)_?glofas.*$", "", str(s))
    s = re.sub(r"\.(xlsx|xls|csv)$", "", s, flags=re.I)
    s = re.sub(r"^[0-9a-f]{8}-", "", s)                      # upload prefixes
    return s.strip().upper()


def _to_numeric(df: pd.DataFrame) -> pd.DataFrame:
    return df.apply(lambda c: pd.to_numeric(c, errors="coerce"))


def load_observations(src, name: str | None = None) -> pd.DataFrame:
    """Observed discharge, wide format: first column = date, one column per station.

    Returns a DataFrame indexed by date with UPPER-CASE station names.
    """
    df = _read_any(src, name)
    df = df.rename(columns={df.columns[0]: "Date"})
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.dropna(subset=["Date"]).set_index("Date").sort_index()
    df.columns = [_clean_station(c) for c in df.columns]
    df = _to_numeric(df)
    df[df < 0] = np.nan
    return df


def load_glofas(src, name: str | None = None) -> tuple[str, pd.DataFrame]:
    """GloFAS forecasts for ONE station: date, then lead 1 ... lead 7 (m3/s).

    The 2nd column may be named after the station (as in the IGEBU files);
    it is the 1-day lead. Returns (STATION, DataFrame[LT_1J..LT_7J]).
    """
    df = _read_any(src, name)
    if df.shape[1] < 8:
        raise ValueError(f"{name}: expected 8 columns (date + 7 lead times), found {df.shape[1]}")
    first = str(df.columns[1])
    station = _clean_station(first) if not first.upper().startswith("LT_") else _clean_station(name or "STATION")
    df = df.iloc[:, :8].copy()
    df.columns = ["Date"] + LT_COLS
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.dropna(subset=["Date"]).set_index("Date").sort_index()
    return station, _to_numeric(df)


def merge_station(obs: pd.DataFrame, glofas: pd.DataFrame, station: str) -> pd.DataFrame:
    """Dates where the observation and all 7 lead times exist (as in the paper)."""
    if station not in obs.columns:
        raise KeyError(f"Station {station} not found in the observation file")
    d = glofas.join(obs[[station]].rename(columns={station: "OBS"}), how="left")
    d = d[["OBS"] + LT_COLS].dropna()
    return d


def qc_report(obs: pd.DataFrame, glofas: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Inventory and simple quality flags for every station."""
    rows = []
    for st in sorted(set(obs.columns) | set(glofas)):
        o = obs[st].dropna() if st in obs.columns else pd.Series(dtype=float)
        g = glofas.get(st)
        m = merge_station(obs, g, st) if (g is not None and st in obs.columns) else pd.DataFrame()
        flags = []
        if g is not None:
            lt1 = g["LT_1J"].dropna()
            if len(lt1):
                med = lt1.median()
                n_out = int((lt1 > 10 * med).sum())
                if n_out:
                    flags.append(f"{n_out} GloFAS value(s) > 10x median")
        if len(m):
            ratio = m["LT_1J"].mean() / m["OBS"].mean()
            if ratio > 3 or ratio < 1 / 3:
                flags.append(f"GloFAS/obs mean ratio = {ratio:.1f} (check grid cell)")
        if len(o) and len(m) < 100:
            flags.append("fewer than 100 common dates")
        rows.append({
            "Station": st,
            "Obs start": o.index.min().date() if len(o) else None,
            "Obs end": o.index.max().date() if len(o) else None,
            "Obs n": len(o),
            "GloFAS file": "yes" if g is not None else "no",
            "Common dates": len(m),
            "Obs mean (m³/s)": round(m["OBS"].mean(), 2) if len(m) else None,
            "GloFAS mean (m³/s)": round(m["LT_1J"].mean(), 2) if len(m) else None,
            "Usable": len(m) >= 100,
            "Flags": "; ".join(flags),
        })
    return pd.DataFrame(rows)


def load_sample(folder: str | Path):
    """Load every *_Glofas file and the observation file of a folder."""
    folder = Path(folder)
    obs_file = next((f for f in folder.iterdir() if "observation" in f.name.lower()), None)
    obs = load_observations(obs_file) if obs_file else None
    gl = {}
    for f in sorted(folder.iterdir()):
        if "glofas" in f.name.lower():
            st, g = load_glofas(f, f.name)
            gl[st] = g
    return obs, gl
