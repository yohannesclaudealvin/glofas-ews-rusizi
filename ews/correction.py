"""Real-time updating of GloFAS forecasts (Section 2.3.2 of the paper).

Historical (verification) form, for each lead time L:

    Qcorr_L(t) = Qglofas_L(t) + [ Qobs(t - L) - Qglofas_L(t - L) ]

i.e. the error made by the L-day forecast L time steps earlier is added to the
current L-day forecast. Time steps are the dates of the record.

Operational form (forecast issued today t0, valid t0 + L):

    Qcorr(t0 + L) = Qglofas_L(t0 + L) + [ Qobs(t0) - Qglofas_L(t0) ]

where Qglofas_L(t0) is the L-day forecast that was valid today (issued L days
ago). When that archived forecast is not available, the current GloFAS value
for today is used instead: e = Qobs(t0) - Qglofas(t0).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import LEADS, LT_COLS
from .metrics import continuous_scores


def realtime_update(sim: pd.Series, obs: pd.Series, L: int) -> pd.Series:
    err = obs - sim
    return sim + err.shift(L)


def correct_station(merged: pd.DataFrame) -> pd.DataFrame:
    """Add COR_1J ... COR_7J (corrected) and PER_1J ... PER_7J (persistence)."""
    d = merged.copy()
    for L in LEADS:
        d[f"COR_{L}J"] = realtime_update(d[f"LT_{L}J"], d["OBS"], L)
        d[f"PER_{L}J"] = d["OBS"].shift(L)          # benchmark: last observation, L steps earlier
    return d


def performance_table(corrected: pd.DataFrame, station: str) -> pd.DataFrame:
    rows = []
    for L in LEADS:
        for kind, col in (("Corrected", f"COR_{L}J"), ("Raw GloFAS", f"LT_{L}J"), ("Persistence", f"PER_{L}J")):
            sc = continuous_scores(corrected[col], corrected["OBS"])
            rows.append({"Station": station, "Lead": L, "LeadTime": f"{L}D", "Series": kind, **sc})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Operational forecast
# ---------------------------------------------------------------------------
ENS_COLS = ["river_discharge", "river_discharge_min", "river_discharge_p25", "river_discharge_median",
            "river_discharge_p75", "river_discharge_max"]


def operational_forecast(fc: pd.DataFrame, today: pd.Timestamp, q_obs_today: float,
                         archive: pd.DataFrame | None = None, station: str | None = None) -> pd.DataFrame:
    """Correct a GloFAS forecast issued today with today's observation.

    fc      : DataFrame indexed by date (daily), columns from the GloFAS API
              (river_discharge and, optionally, ensemble statistics).
    archive : optional archive of past forecasts with columns
              station, issue_date, valid_date, lead, q  (see ForecastArchive).
              If the L-day forecast valid today exists, the same-lead error of
              the paper is used for lead L; otherwise the error of today's value.
    Returns one row per lead 1..7 with raw and corrected values and the error used.
    """
    today = pd.Timestamp(today).normalize()
    if today not in fc.index:
        raise ValueError(f"The GloFAS series does not contain today's date {today.date()}")
    q_today = float(fc.loc[today, "river_discharge"])
    rows = []
    for L in LEADS:
        tv = today + pd.Timedelta(days=L)
        if tv not in fc.index:
            continue
        err, method = q_obs_today - q_today, "erreur sur la valeur GloFAS du jour"
        if archive is not None and len(archive):
            a = archive[(archive["valid_date"] == today) & (archive["lead"] == L)]
            if station is not None:
                a = a[a["station"] == station]
            if len(a):
                err = q_obs_today - float(a.sort_values("issue_date")["q"].iloc[-1])
                method = f"erreur de même échéance (prévision à {L} j archivée)"
        r = {"lead": L, "valid_date": tv.date(), "glofas_raw": float(fc.loc[tv, "river_discharge"]),
             "error_added": err, "method": method}
        r["corrected"] = max(r["glofas_raw"] + err, 0.0)
        for c in ENS_COLS[1:]:
            if c in fc.columns:
                r[c.replace("river_discharge_", "cor_")] = max(float(fc.loc[tv, c]) + err, 0.0)
        rows.append(r)
    return pd.DataFrame(rows)


class ForecastArchive:
    """Archive of issued forecasts (station, issue_date, valid_date, lead, q).

    Saving every day's raw GloFAS forecast is what allows the same-lead error of
    the paper to be used operationally L days later.
    """
    COLS = ["station", "issue_date", "valid_date", "lead", "q"]

    def __init__(self, df: pd.DataFrame | None = None):
        self.df = pd.DataFrame(columns=self.COLS) if df is None else self._norm(df)

    @staticmethod
    def _norm(df):
        df = df[ForecastArchive.COLS].copy()
        df["issue_date"] = pd.to_datetime(df["issue_date"]).dt.normalize()
        df["valid_date"] = pd.to_datetime(df["valid_date"]).dt.normalize()
        df["lead"] = df["lead"].astype(int)
        return df

    def add(self, station: str, today, fc: pd.DataFrame):
        today = pd.Timestamp(today).normalize()
        new = [{"station": station, "issue_date": today, "valid_date": today + pd.Timedelta(days=L), "lead": L,
                "q": float(fc.loc[today + pd.Timedelta(days=L), "river_discharge"])}
               for L in LEADS if today + pd.Timedelta(days=L) in fc.index]
        self.df = pd.concat([self.df, pd.DataFrame(new)], ignore_index=True) if len(self.df) else pd.DataFrame(new)
        self.df = self._norm(self.df).drop_duplicates(["station", "issue_date", "lead"], keep="last")
        return self

    def to_csv(self) -> bytes:
        return self.df.to_csv(index=False).encode()
