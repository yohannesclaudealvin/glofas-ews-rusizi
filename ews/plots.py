"""Plotly figures used by the app (same colour code as the paper)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go

OBS, RAW, COR, PER = "#d62728", "#222222", "#1f4fd1", "#eb6834"
ALERT_COLORS = {"Normal": "#2e9d4a", "Vigilance": "#e6b400", "Alerte": "#ef7d18", "Alerte maximale": "#c8102e"}


def heatmap(df: pd.DataFrame, value: str, row: str = "Station", col: str = "LeadTime", digits: int = 2,
            title: str | None = None, reverse: bool = False, height: int = 320):
    p = df.pivot(index=row, columns=col, values=value)
    p = p[sorted(p.columns, key=lambda c: int(str(c).rstrip("D")))]
    z = p.values.astype(float)
    rng = {"KGE": (-1, 1), "NSE": (-1, 1)}.get(value, (None, None))
    fig = go.Figure(go.Heatmap(z=z, x=list(p.columns), y=list(p.index), colorscale="Spectral", zmin=rng[0], zmax=rng[1],
                               reversescale=reverse, text=np.round(z, digits), texttemplate="%{text}",
                               textfont={"size": 13}, colorbar={"title": value}, xgap=2, ygap=2))
    fig.update_layout(title=title or value, height=height, margin=dict(l=10, r=10, t=40, b=10),
                      xaxis_title="Lead time", yaxis_title=None)
    return fig


def hydrograph(d: pd.DataFrame, lead: int, title: str = ""):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=d.index, y=d["OBS"], name="Observed", line=dict(color=OBS, width=1.4)))
    fig.add_trace(go.Scatter(x=d.index, y=d[f"LT_{lead}J"], name="Simulated (raw GloFAS)", line=dict(color=RAW, width=1.2)))
    fig.add_trace(go.Scatter(x=d.index, y=d[f"COR_{lead}J"], name="Corrected simulation", line=dict(color=COR, width=1.4)))
    fig.update_layout(title=title, height=380, yaxis_title="Discharge (m³/s)", hovermode="x unified",
                      legend=dict(orientation="h", y=1.08), margin=dict(l=10, r=10, t=50, b=10))
    return fig


def lead_lines(perf: pd.DataFrame, metric: str):
    fig = go.Figure()
    for s, c in (("Corrected", COR), ("Raw GloFAS", RAW), ("Persistence", PER)):
        d = perf[perf["Series"] == s]
        fig.add_trace(go.Scatter(x=d["Lead"], y=d[metric], name=s, mode="lines+markers", line=dict(color=c, width=2)))
    fig.update_layout(height=300, title=metric, xaxis_title="Lead time (days)", margin=dict(l=10, r=10, t=40, b=10),
                      legend=dict(orientation="h", y=-0.3))
    return fig


def forecast_chart(station: str, past: pd.Series, res: pd.DataFrame, q_obs: float, today, thresholds: dict):
    fig = go.Figure()
    x = pd.to_datetime(res["valid_date"])
    xs = [pd.Timestamp(today)] + list(x)
    if "cor_min" in res and "cor_max" in res:
        fig.add_trace(go.Scatter(x=list(x) + list(x[::-1]), y=list(res["cor_max"]) + list(res["cor_min"][::-1]),
                                 fill="toself", fillcolor="rgba(31,79,209,0.12)", line=dict(width=0), mode="lines",
                                 name="Ensemble min–max (corrigé)", hoverinfo="skip"))
    if "cor_p25" in res and "cor_p75" in res:
        fig.add_trace(go.Scatter(x=list(x) + list(x[::-1]), y=list(res["cor_p75"]) + list(res["cor_p25"][::-1]),
                                 fill="toself", fillcolor="rgba(31,79,209,0.25)", line=dict(width=0), mode="lines",
                                 name="Ensemble p25–p75 (corrigé)", hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=x, y=res["glofas_raw"], name="GloFAS brut", mode="lines+markers",
                             line=dict(color=RAW, dash="dot")))
    fig.add_trace(go.Scatter(x=xs, y=[q_obs] + list(res["corrected"]), name="Prévision corrigée",
                             mode="lines+markers", line=dict(color=COR, width=3)))
    fig.add_trace(go.Scatter(x=[pd.Timestamp(today)], y=[q_obs], name="Observé aujourd'hui", mode="markers",
                             marker=dict(color=OBS, size=12, symbol="diamond")))
    if past is not None and len(past):
        fig.add_trace(go.Scatter(x=past.index, y=past.values, name="Observé (récent)", line=dict(color=OBS, width=1.5)))
    cols = {"Vigilance": "#e6b400", "Alerte": "#ef7d18", "Alerte maximale": "#c8102e"}
    pos = {"Vigilance": "bottom left", "Alerte": "bottom right", "Alerte maximale": "top right"}
    for lab, val in thresholds.items():
        col = cols.get(lab, "#888")
        if val is not None and np.isfinite(val):
            fig.add_hline(y=val, line=dict(color=col, dash="dash", width=1.5), annotation_text=f"{lab} ({val:.1f})",
                          annotation_position=pos.get(lab, "top left"), annotation_font_color=col)
    fig.update_layout(title=station, height=380, yaxis_title="Débit (m³/s)", hovermode="x unified",
                      legend=dict(orientation="h", y=-0.25), margin=dict(l=10, r=10, t=50, b=10))
    return fig
