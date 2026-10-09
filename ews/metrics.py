"""Performance criteria (same definitions as hydroGOF / the paper)."""
from __future__ import annotations

import numpy as np
import pandas as pd


def _clean(sim, obs):
    s = np.asarray(sim, float); o = np.asarray(obs, float)
    ok = np.isfinite(s) & np.isfinite(o)
    return s[ok], o[ok]


def kge(sim, obs):
    """Kling-Gupta efficiency (Gupta et al., 2009)."""
    s, o = _clean(sim, obs)
    if len(s) < 3: return np.nan
    r = np.corrcoef(s, o)[0, 1]
    return 1 - np.sqrt((r - 1) ** 2 + (s.std(ddof=1) / o.std(ddof=1) - 1) ** 2 + (s.mean() / o.mean() - 1) ** 2)


def nse(sim, obs):
    """Nash-Sutcliffe efficiency."""
    s, o = _clean(sim, obs)
    if len(s) < 3: return np.nan
    return 1 - np.sum((s - o) ** 2) / np.sum((o - o.mean()) ** 2)


def pbias(sim, obs):
    """Percent bias, 100 * sum(sim - obs) / sum(obs)."""
    s, o = _clean(sim, obs)
    return 100 * np.sum(s - o) / np.sum(o) if len(s) else np.nan


def rmse(sim, obs):
    s, o = _clean(sim, obs)
    return float(np.sqrt(np.mean((s - o) ** 2))) if len(s) else np.nan


def rsr(sim, obs):
    """RMSE divided by the standard deviation of observations (Moriasi et al., 2007)."""
    s, o = _clean(sim, obs)
    return rmse(s, o) / o.std(ddof=1) if len(s) > 2 else np.nan


def continuous_scores(sim, obs) -> dict:
    return {"KGE": kge(sim, obs), "NSE": nse(sim, obs), "PBIAS": pbias(sim, obs),
            "RSR": rsr(sim, obs), "RMSE": rmse(sim, obs)}


def contingency(obs_event, fc_event) -> dict:
    """2x2 contingency scores.

    a = hit, b = false alarm, c = miss, d = correct negative.
    FAR      = false-alarm RATE b/(b+d)  (as used in Figure 4 of the paper)
    FAR_ratio= false-alarm RATIO b/(a+b)
    LR       = POD / FAR  (likelihood ratio, "RV" in the paper text)
    ROC      = POD - FAR  (ROC skill / Peirce score)
    """
    o = pd.Series(obs_event).astype("boolean"); f = pd.Series(fc_event).astype("boolean")
    ok = o.notna().values & f.notna().values
    o = o[ok].astype(bool).values; f = f[ok].astype(bool).values
    a = int(np.sum(o & f)); b = int(np.sum(~o & f)); c = int(np.sum(o & ~f)); d = int(np.sum(~o & ~f))
    div = lambda x, y: 100 * x / y if y else np.nan
    pod = div(a, a + c); far = div(b, b + d)
    return {"a": a, "b": b, "c": c, "d": d, "POD": pod, "FAR": far,
            "LR": pod / far if (far == far and far > 0) else np.nan,
            "ROC": pod - far if pod == pod and far == far else np.nan,
            "FAR_ratio": div(b, a + b), "CSI": div(a, a + b + c)}
