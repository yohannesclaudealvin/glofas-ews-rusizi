"""Trend tests, flood frequency analysis and critical days (Section 2.3.4)."""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from .metrics import contingency


# ---------------------------------------------------------------------------
# Trends
# ---------------------------------------------------------------------------
def sen_slope(x) -> float:
    x = np.asarray(x, float); n = len(x)
    s = [(x[j] - x[i]) / (j - i) for i in range(n - 1) for j in range(i + 1, n)]
    return float(np.median(s))


def mk_hamed_rao(x, alpha: float = 0.05) -> dict:
    """Modified Mann-Kendall test (Hamed & Rao, 1998), as pymannkendall/modifiedmk."""
    x = np.asarray(x, float); x = x[np.isfinite(x)]; n = len(x)
    if n < 4:
        return {"n": n, "S": np.nan, "z": np.nan, "p": np.nan, "sen_slope": np.nan, "trend": "insufficient data"}
    S = sum(np.sign(x[k + 1:] - x[k]).sum() for k in range(n - 1))
    _, tp = np.unique(x, return_counts=True)
    var_s = (n * (n - 1) * (2 * n + 5) - np.sum(tp * (tp - 1) * (2 * tp + 5))) / 18
    slope = sen_slope(x)
    R = stats.rankdata(x - np.arange(1, n + 1) * slope)
    y = R - R.mean()
    acf = np.correlate(y, y, "full")[n - 1:] / n
    acf = acf / acf[0]
    lim = stats.norm.ppf(1 - alpha / 2) / np.sqrt(n)
    sni = sum((n - i) * (n - i - 1) * (n - i - 2) * acf[i] for i in range(1, n) if abs(acf[i]) > lim)
    var_s *= 1 + 2 / (n * (n - 1) * (n - 2)) * sni
    z = (S - np.sign(S)) / np.sqrt(var_s) if S != 0 else 0.0
    p = 2 * (1 - stats.norm.cdf(abs(z)))
    trend = ("increasing" if z > 0 else "decreasing") if p < alpha else "no trend"
    return {"n": n, "S": float(S), "z": float(z), "p": float(p), "sen_slope": slope, "trend": trend}


# ---------------------------------------------------------------------------
# Frequency analysis
# ---------------------------------------------------------------------------
def annual_series(obs: pd.Series, start: int | None = None, end: int | None = None,
                  min_fraction: float = 0.0) -> pd.DataFrame:
    """Annual maxima and means. Years with fewer observations than
    min_fraction x the median yearly count are dropped (0 = keep all, as in the paper)."""
    o = obs.dropna()
    g = o.groupby(o.index.year)
    df = pd.DataFrame({"AMAX": g.max(), "MEAN": g.mean(), "n_obs": g.count()})
    if start: df = df[df.index >= start]
    if end: df = df[df.index <= end]
    return df[df["n_obs"] >= min_fraction * df["n_obs"].median()]


def fit_distributions(amax) -> dict:
    """MLE fits of Gumbel, GEV and Normal, with AIC/BIC and return-period quantiles."""
    x = np.asarray(amax, float); n = len(x)
    out = {}
    for name, dist, k in (("Gumbel", stats.gumbel_r, 2), ("GEV", stats.genextreme, 3), ("Normal", stats.norm, 2)):
        p = dist.fit(x)
        ll = float(np.sum(dist.logpdf(x, *p)))
        out[name] = {"params": p, "AIC": 2 * k - 2 * ll, "BIC": k * np.log(n) - 2 * ll,
                     "q": (lambda T, dist=dist, p=p: float(dist.ppf(1 - 1 / T, *p)))}
    out["best"] = min(("Gumbel", "GEV", "Normal"), key=lambda m: out[m]["AIC"])
    return out


def frequency_table(obs: pd.Series, station: str, periods=(2, 5, 10, 25, 50, 100), q_crit: float = 0.9,
                    min_fraction: float = 0.0, start: int | None = None, end: int | None = None) -> tuple[pd.DataFrame, dict]:
    am = annual_series(obs, start, end, min_fraction)
    fits = fit_distributions(am["AMAX"])
    row = {"Station": station, "n_years": len(am), "Best (AIC)": fits["best"]}
    for m in ("Gumbel", "GEV", "Normal"):
        row[f"AIC {m}"] = fits[m]["AIC"]
    for T in periods:
        row[f"Q{T} Gumbel"] = fits["Gumbel"]["q"](T)
    for T in periods:
        row[f"Q{T} GEV"] = fits["GEV"]["q"](T)
    row[f"Q{int(q_crit*100)} (alert)"] = float(obs.dropna().quantile(q_crit))
    return pd.DataFrame([row]), fits


def critical_days(obs: pd.Series, q_crit: float = 0.9) -> pd.DataFrame:
    o = obs.dropna(); thr = o.quantile(q_crit)
    c = o[o >= thr]
    by_m = c.groupby(c.index.month).count().reindex(range(1, 13), fill_value=0)
    return pd.DataFrame({"Month": range(1, 13), "CriticalDays": by_m.values})


def detection_table(corrected: pd.DataFrame, threshold: float, station: str, leads=(1, 3, 5, 7), q_raw: float = 0.9) -> pd.DataFrame:
    rows = []
    for L in leads:
        c = corrected[f"COR_{L}J"]; ok = c.notna()
        ob = corrected["OBS"][ok] >= threshold
        r1 = contingency(ob, c[ok] >= threshold)
        raw = corrected[f"LT_{L}J"][ok]
        r2 = contingency(ob, raw >= raw.quantile(q_raw))
        rows.append({"Station": station, "Lead": L, "Events": int(ob.sum()),
                     "POD corrected": r1["POD"], "FAR ratio corrected": r1["FAR_ratio"], "CSI corrected": r1["CSI"],
                     "POD raw": r2["POD"], "FAR ratio raw": r2["FAR_ratio"], "CSI raw": r2["CSI"]})
    return pd.DataFrame(rows)
