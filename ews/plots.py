"""Interactive Plotly figures (clean, uncluttered, shared theme)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from . import theme as T

# metric -> (colourscale, zmin, zmax, digits, higher_is_better)
SCALES = {
    "KGE": (T.DIVERGING, -1, 1, 2), "NSE": (T.DIVERGING, -1, 1, 2),
    "PBIAS": (T.DIVERGING[::-1], None, None, 1), "RSR": (None, 0, 2, 2),
    "POD": (T.SEQ_BLUE, 0, 100, 1), "CSI": (T.SEQ_BLUE, 0, 100, 1), "ROC": (T.SEQ_BLUE, 0, 100, 1),
    "FAR": (T.SEQ_ORANGE, 0, None, 1), "FAR_ratio": (T.SEQ_ORANGE, 0, 100, 1), "LR": (T.SEQ_BLUE, 0, None, 1),
}
LABELS = {"KGE": "KGE", "NSE": "NSE", "PBIAS": "PBIAS (%)", "RSR": "RSR", "POD": "POD (%)", "FAR": "FAR – taux (%)",
          "LR": "LR = POD/FAR", "ROC": "ROC = POD − FAR", "CSI": "CSI (%)", "FAR_ratio": "FAR – ratio (%)"}


def _rgb(c):
    c = c.lstrip("#"); return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


def _interp(scale, t):
    t = min(max(t, 0), 1)
    for (a, ca), (b, cb) in zip(scale[:-1], scale[1:]):
        if a <= t <= b:
            f = 0 if b == a else (t - a) / (b - a)
            x, y = _rgb(ca), _rgb(cb)
            return tuple(int(x[i] + f * (y[i] - x[i])) for i in range(3))
    return _rgb(scale[-1][1])


def heatmap(df: pd.DataFrame, value: str, row: str = "Station", col: str = "LeadTime", height: int | None = None,
            title: str | None = None):
    """Station x lead-time grid with readable cell labels (dark text on light cells, white on dark)."""
    p = df.pivot(index=row, columns=col, values=value)
    p = p[sorted(p.columns, key=lambda c: int(str(c).rstrip("D")))]
    z = p.values.astype(float)
    scale, zmin, zmax, dig = SCALES.get(value, (T.SEQ_BLUE, None, None, 2))
    if value == "PBIAS":
        m = np.nanmax(np.abs(z)) if np.isfinite(z).any() else 1
        zmin, zmax = -max(m, 1), max(m, 1)
    if value == "RSR":
        scale = [[0, "#184f95"], [0.25, "#86b6ef"], [0.5, "#f0efec"], [0.75, "#e88a85"], [1, "#b2272f"]]
    lo = np.nanmin(z) if zmin is None else zmin
    hi = np.nanmax(z) if zmax is None else zmax
    if not np.isfinite(hi) or hi == lo: hi = lo + 1
    fig = go.Figure(go.Heatmap(z=z, x=list(p.columns), y=list(p.index), colorscale=scale, zmin=lo, zmax=hi,
                               xgap=3, ygap=3, colorbar=dict(thickness=10, len=0.9, outlinewidth=0),
                               hovertemplate=f"%{{y}} · %{{x}}<br>{value} = %{{z:.{dig}f}}<extra></extra>"))
    for i, r in enumerate(p.index):
        for j, c in enumerate(p.columns):
            v = z[i, j]
            if not np.isfinite(v): continue
            rgb = _interp(scale, (v - lo) / (hi - lo))
            lum = 0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]
            fig.add_annotation(x=c, y=r, text=f"{v:.{dig}f}", showarrow=False,
                               font=dict(size=12, color="white" if lum < 140 else T.INK))
    fig.update_layout(title=title or LABELS.get(value, value), height=height or (110 + 42 * len(p.index)),
                      xaxis=dict(title="Échéance", showline=False, ticks=""), yaxis=dict(showgrid=False),
                      margin=dict(l=10, r=10, t=50, b=10))
    return fig


def hydrograph(d: pd.DataFrame, lead: int, title: str = "", show_raw: bool = False):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=d.index, y=d[f"LT_{lead}J"], name="GloFAS brut",
                             line=dict(color=T.RAW, width=1.2, dash="dot"), visible=True if show_raw else "legendonly"))
    fig.add_trace(go.Scatter(x=d.index, y=d[f"COR_{lead}J"], name=f"GloFAS corrigé ({lead} j)",
                             line=dict(color=T.BLUE, width=2.2), opacity=0.85))
    fig.add_trace(go.Scatter(x=d.index, y=d["OBS"], name="Observé", line=dict(color=T.INK, width=1.2)))
    fig.update_layout(title=title, height=450, yaxis_title="Débit (m³/s)", hovermode="x unified",
                      legend=dict(x=1, xanchor="right", y=1.02, yanchor="bottom"),
                      xaxis=dict(rangeslider=dict(visible=True, thickness=0.06),
                                 rangeselector=dict(x=0, y=1.02, yanchor="bottom", bgcolor="#f3f6fa",
                                                    buttons=[dict(count=1, label="1 an", step="year", stepmode="backward"),
                                                             dict(count=3, label="3 ans", step="year", stepmode="backward"),
                                                             dict(step="all", label="Tout")])),
                      margin=dict(l=10, r=10, t=80, b=10))
    return fig


def obs_series(s: pd.Series, title: str = ""):
    fig = go.Figure(go.Scatter(x=s.index, y=s.values, name="Débit observé", line=dict(color=T.INK, width=1.3),
                               fill="tozeroy", fillcolor="rgba(31,41,55,0.05)"))
    fig.update_layout(title=title, height=330, yaxis_title="Débit (m³/s)", hovermode="x unified", showlegend=False,
                      xaxis=dict(rangeslider=dict(visible=True, thickness=0.06)))
    return fig


def lead_lines(perf: pd.DataFrame, metric: str):
    fig = go.Figure()
    styles = {"Corrected": ("GloFAS corrigé", T.BLUE, "solid"), "Persistence": ("Persistance", T.ORANGE, "solid"),
              "Raw GloFAS": ("GloFAS brut", T.RAW, "dot")}
    for s, (name, col, dash) in styles.items():
        d = perf[perf["Series"] == s]
        fig.add_trace(go.Scatter(x=d["Lead"], y=d[metric], name=name, mode="lines+markers",
                                 line=dict(color=col, width=2.4, dash=dash), marker=dict(size=7),
                                 visible=True if s != "Raw GloFAS" else "legendonly"))
    fig.update_layout(title=LABELS.get(metric, metric), height=320, xaxis=dict(title="Échéance (jours)", dtick=1),
                      hovermode="x unified")
    return fig


def annual_max(am: pd.DataFrame, quantiles: dict, title: str):
    fig = go.Figure(go.Scatter(x=am.index, y=am["AMAX"], mode="lines+markers", name="Maximum annuel observé",
                               line=dict(color=T.INK, width=2), marker=dict(size=7)))
    for (lab, v), dash in zip(quantiles.items(), ("dot", "dash", "dashdot")):
        fig.add_hline(y=v, line=dict(color=T.BLUE, dash=dash, width=1.4), annotation_text=f"{lab} : {v:.1f}",
                      annotation_position="top left", annotation_font_color=T.BLUE_DARK)
    fig.update_layout(title=title, height=360, yaxis_title="Débit (m³/s)", showlegend=False)
    return fig


def monthly_bars(cd: pd.DataFrame, title: str):
    months = ["Jan", "Fév", "Mar", "Avr", "Mai", "Juin", "Juil", "Août", "Sep", "Oct", "Nov", "Déc"]
    fig = go.Figure(go.Bar(x=months, y=cd["CriticalDays"], marker=dict(color=T.BLUE, cornerradius=4),
                           hovertemplate="%{x} : %{y} jours<extra></extra>"))
    fig.update_layout(title=title, height=360, yaxis_title="Jours critiques", bargap=0.25)
    return fig


def forecast_chart(station: str, res: pd.DataFrame, q_obs: float, today, thresholds: dict):
    fig = go.Figure()
    x = list(pd.to_datetime(res["valid_date"]))
    if {"cor_min", "cor_max"} <= set(res.columns):
        fig.add_trace(go.Scatter(x=x + x[::-1], y=list(res["cor_max"]) + list(res["cor_min"][::-1]), fill="toself",
                                 fillcolor=T.BAND, line=dict(width=0), mode="lines", name="Ensemble min–max",
                                 hoverinfo="skip"))
    if {"cor_p25", "cor_p75"} <= set(res.columns):
        fig.add_trace(go.Scatter(x=x + x[::-1], y=list(res["cor_p75"]) + list(res["cor_p25"][::-1]), fill="toself",
                                 fillcolor=T.BAND_IQR, line=dict(width=0), mode="lines", name="Ensemble p25–p75",
                                 hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=x, y=res["glofas_raw"], name="GloFAS brut", mode="lines",
                             line=dict(color=T.RAW, dash="dot"), visible="legendonly"))
    fig.add_trace(go.Scatter(x=[pd.Timestamp(today)] + x, y=[q_obs] + list(res["corrected"]), name="Prévision corrigée",
                             mode="lines+markers", line=dict(color=T.BLUE, width=3), marker=dict(size=7)))
    fig.add_trace(go.Scatter(x=[pd.Timestamp(today)], y=[q_obs], name="Observé aujourd'hui", mode="markers",
                             marker=dict(color=T.INK, size=13, symbol="diamond")))
    for lab, v in thresholds.items():
        if v is not None and np.isfinite(v):
            fig.add_hline(y=v, line=dict(color=T.STATUS.get(lab, "#888"), dash="dash", width=1.4),
                          annotation_text=f"{T.ICONS.get(lab, '')} {lab} ({v:.1f})", annotation_position="top left",
                          annotation_font_color=T.STATUS.get(lab, "#555"))
    fig.update_layout(title=f"{station} – prévision corrigée à 7 jours", height=420, yaxis_title="Débit (m³/s)",
                      hovermode="x unified")
    return fig


def basin_map_plotly(meta: pd.DataFrame, color_col: str | None = None):
    """Small overview map of all stations (Plotly, no API key)."""
    m = meta.dropna(subset=["lat", "lon"])
    fig = go.Figure(go.Scattermap(lat=m["lat"], lon=m["lon"], mode="markers+text", text=m["station"],
                                  textposition="top right", marker=dict(size=13, color=T.BLUE),
                                  hovertemplate="%{text}<br>%{lat:.3f}, %{lon:.3f}<extra></extra>"))
    fig.update_layout(map=dict(style="open-street-map", center=dict(lat=m["lat"].mean() if len(m) else -3.2,
                                                                     lon=m["lon"].mean() if len(m) else 29.3), zoom=8.3),
                      height=430, margin=dict(l=0, r=0, t=0, b=0), showlegend=False)
    return fig
