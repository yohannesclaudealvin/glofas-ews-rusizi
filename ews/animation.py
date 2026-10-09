"""Animated river maps: how the discharge of each river changes over time.

Two outputs built from the same frames:
* an interactive Plotly figure (map + hydrograph) with a Play button and a date slider,
  downloadable as a standalone HTML page;
* an animated GIF (matplotlib), to drop into a report or a WhatsApp message.

Each station is described by a dict:
    {"name", "river", "lat", "lon", "ways": [{"coords": [[lat, lon], ...]}, ...],
     "series": pd.Series (date -> discharge), "th": {"Jaune": q, "Orange": q, "Rouge": q}}
The river line of a station takes the colour of its alert level at each date and gets thicker
when the discharge rises.
"""
from __future__ import annotations

import io

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from . import theme as T

LEVEL_COLORS = {"Vert": "#0ca30c", "Jaune": "#fab219", "Orange": "#ec835a", "Rouge": "#d03b3b"}
ORDER = ["Vert", "Jaune", "Orange", "Rouge"]


def level(q, th: dict) -> str:
    lv = "Vert"
    for n in ("Jaune", "Orange", "Rouge"):
        v = th.get(n)
        if v is not None and q is not None and np.isfinite(q) and q >= v:
            lv = n
    return lv


def relative_thresholds(series: pd.Series) -> dict:
    """Fallback thresholds when none are known: 75th, 90th and 97th percentiles of the series shown."""
    s = series.dropna()
    if len(s) < 5:
        return {}
    return {"Jaune": float(s.quantile(0.75)), "Orange": float(s.quantile(0.90)), "Rouge": float(s.quantile(0.97))}


def frame_dates(series_list: list[pd.Series], start=None, end=None, max_frames: int = 120) -> list[pd.Timestamp]:
    idx = sorted(set().union(*[set(s.dropna().index) for s in series_list])) if series_list else []
    idx = [d for d in idx if (start is None or d >= pd.Timestamp(start)) and (end is None or d <= pd.Timestamp(end))]
    if len(idx) > max_frames:
        step = int(np.ceil(len(idx) / max_frames))
        idx = idx[::step]
    return [pd.Timestamp(d) for d in idx]


def _value(s: pd.Series, d):
    """Value at date d (last known value, at most 7 days old)."""
    s = s.dropna()
    s = s[s.index <= d]
    if not len(s) or (d - s.index[-1]).days > 7:
        return np.nan
    return float(s.iloc[-1])


def _line(ways):
    lat, lon = [], []
    for w in ways:
        for c in w["coords"]:
            lat.append(c[0]); lon.append(c[1])
        lat.append(None); lon.append(None)
    return lat, lon


def _width(q, s: pd.Series):
    s = s.dropna()
    if not len(s) or not np.isfinite(q):
        return 2.0
    lo, hi = float(s.min()), float(s.max())
    return 2.0 + 10.0 * (q - lo) / (hi - lo) if hi > lo else 4.0


def _center(stations):
    pts = [(s["lat"], s["lon"]) for s in stations] + \
          [(c[0], c[1]) for s in stations for w in s.get("ways") or [] for c in w["coords"][::5]]
    la = [p[0] for p in pts]; lo = [p[1] for p in pts]
    span = max(max(la) - min(la), max(lo) - min(lo), 0.05)
    zoom = float(np.clip(np.log2(360 / span) - 1.3, 6, 13))
    return dict(lat=(min(la) + max(la)) / 2, lon=(min(lo) + max(lo)) / 2), zoom


def animated_figure(stations: list[dict], dates: list[pd.Timestamp], focus: int = 0, title: str = "",
                    unit: str = "m³/s", other_ways: list[dict] | None = None, height: int = 720) -> go.Figure:
    """Map (top) + hydrograph of the focus station (bottom), one frame per date, with Play/slider."""
    fs = stations[focus]
    fig = make_subplots(rows=2, cols=1, row_heights=[0.68, 0.32], vertical_spacing=0.07,
                        specs=[[{"type": "map"}], [{"type": "xy"}]])
    # static background: other rivers
    if other_ways:
        la, lo = _line(other_ways)
        fig.add_trace(go.Scattermap(lat=la, lon=lo, mode="lines", line=dict(color="#a9c8ee", width=1),
                                    hoverinfo="skip", showlegend=False), row=1, col=1)
    n_static = len(fig.data)

    def dyn_traces(d):
        out = []
        for s in stations:
            q = _value(s["series"], d)
            lv = level(q, s["th"]) if np.isfinite(q) else None
            col = LEVEL_COLORS[lv] if lv else "#9aa3ad"
            la, lo = _line(s.get("ways") or [])
            out.append(go.Scattermap(lat=la or [None], lon=lo or [None], mode="lines",
                                     line=dict(color=col, width=_width(q, s["series"])),
                                     hoverinfo="skip", showlegend=False))
            txt = f"{s['name']}<br>{q:.1f} {unit}" if np.isfinite(q) else f"{s['name']}<br>—"
            out.append(go.Scattermap(lat=[s["lat"]], lon=[s["lon"]], mode="markers+text",
                                     marker=dict(size=16, color=col), text=[txt], textposition="top right",
                                     textfont=dict(size=12, color=T.INK), hovertext=[txt], hoverinfo="text",
                                     showlegend=False))
        q = _value(fs["series"], d)
        out.append(go.Scatter(x=[d, d], y=[0, ymax], mode="lines", line=dict(color=T.INK, width=1, dash="dot"),
                              hoverinfo="skip", showlegend=False))
        out.append(go.Scatter(x=[d], y=[q], mode="markers", marker=dict(size=11, color=T.INK),
                              hovertemplate="%{x|%d/%m/%Y} : %{y:.1f} " + unit + "<extra></extra>", showlegend=False))
        return out

    ser = fs["series"].dropna()
    ser = ser[(ser.index >= dates[0] - pd.Timedelta(days=1)) & (ser.index <= dates[-1] + pd.Timedelta(days=1))]
    ymax = float(max([ser.max() if len(ser) else 1] + [v for v in fs["th"].values() if v])) * 1.1
    for d in dyn_traces(dates[0]):
        fig.add_trace(d, row=1 if isinstance(d, go.Scattermap) else 2, col=1)
    # hydrograph background: alert bands and full series (static)
    for n, lo_, hi_ in (("Vert", 0, fs["th"].get("Jaune")), ("Jaune", fs["th"].get("Jaune"), fs["th"].get("Orange")),
                        ("Orange", fs["th"].get("Orange"), fs["th"].get("Rouge")), ("Rouge", fs["th"].get("Rouge"), ymax)):
        if lo_ is not None and hi_ is not None and hi_ > lo_:
            fig.add_shape(type="rect", xref="x domain", yref="y", x0=0, x1=1, y0=lo_, y1=hi_, layer="below",
                          fillcolor=LEVEL_COLORS[n], opacity=0.09, line_width=0)
    fig.add_trace(go.Scatter(x=ser.index, y=ser.values, mode="lines", line=dict(color=T.BLUE, width=1.8),
                             name=fs["name"], hovertemplate="%{x|%d/%m/%Y} : %{y:.1f} " + unit + "<extra></extra>",
                             showlegend=False), row=2, col=1)
    dyn_idx = list(range(n_static, n_static + 2 * len(stations) + 2))

    frames = [go.Frame(name=d.strftime("%Y-%m-%d"), data=dyn_traces(d), traces=dyn_idx,
                       layout=dict(title_text=f"{title} — {d:%d/%m/%Y}")) for d in dates]
    fig.frames = frames
    center, zoom = _center(stations)
    steps = [dict(method="animate", label=d.strftime("%d/%m/%y"),
                  args=[[d.strftime("%Y-%m-%d")], dict(mode="immediate", frame=dict(duration=0, redraw=True),
                                                        transition=dict(duration=0))]) for d in dates]
    fig.update_layout(
        title=f"{title} — {dates[0]:%d/%m/%Y}", height=height, margin=dict(l=10, r=10, t=60, b=95),
        map=dict(style="open-street-map", center=center, zoom=zoom),
        yaxis=dict(title=f"Débit ({unit})", range=[0, ymax]),
        xaxis=dict(range=[dates[0] - pd.Timedelta(days=2), dates[-1] + pd.Timedelta(days=2)]),
        updatemenus=[dict(type="buttons", direction="left", x=0, y=-0.07, xanchor="left", yanchor="top",
                          pad=dict(t=0, r=10), showactive=False,
                          buttons=[dict(label="▶ Lecture", method="animate",
                                        args=[None, dict(frame=dict(duration=350, redraw=True), fromcurrent=True,
                                                         transition=dict(duration=0))]),
                                   dict(label="⏸ Pause", method="animate",
                                        args=[[None], dict(frame=dict(duration=0, redraw=False), mode="immediate")])])],
        sliders=[dict(active=0, x=0.17, len=0.83, y=-0.04, yanchor="top", pad=dict(t=8, b=0),
                      ticklen=0, font=dict(size=1, color="rgba(0,0,0,0)"),
                      currentvalue=dict(prefix="Date : ", font=dict(size=13), xanchor="right"), steps=steps)],
    )
    return fig


def animated_gif(stations: list[dict], dates: list[pd.Timestamp], focus: int = 0, title: str = "",
                 unit: str = "m³/s", other_ways: list[dict] | None = None, fps: float = 3.0,
                 max_frames: int = 80) -> bytes:
    """Same animation as an animated GIF (no web map background)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.animation import FuncAnimation, PillowWriter
    import tempfile, os

    if len(dates) > max_frames:
        dates = dates[::int(np.ceil(len(dates) / max_frames))]
    fs = stations[focus]
    fig = plt.figure(figsize=(7.5, 7.2), dpi=110)
    axm = fig.add_axes([0.07, 0.36, 0.88, 0.56])
    axh = fig.add_axes([0.10, 0.07, 0.86, 0.22])
    for w in other_ways or []:
        c = np.array(w["coords"])
        axm.plot(c[:, 1], c[:, 0], color="#bcd4f2", lw=0.8, zorder=1)
    lines, dots, labels = [], [], []
    for s in stations:
        segs = []
        for w in s.get("ways") or []:
            c = np.array(w["coords"])
            segs.append(axm.plot(c[:, 1], c[:, 0], color="#9aa3ad", lw=2, solid_capstyle="round", zorder=2)[0])
        lines.append(segs)
        dots.append(axm.scatter([s["lon"]], [s["lat"]], s=90, color="#9aa3ad", edgecolor="white", zorder=4))
        labels.append(axm.text(s["lon"], s["lat"], "", fontsize=9, ha="left", va="bottom", zorder=5,
                               bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="none", alpha=0.85)))
    pts = [(s["lat"], s["lon"]) for s in stations] + \
          [(c[0], c[1]) for s in stations for w in s.get("ways") or [] for c in w["coords"]]
    la = [p[0] for p in pts]; lo = [p[1] for p in pts]
    pad = max(max(la) - min(la), max(lo) - min(lo)) * 0.08 + 0.01
    axm.set_xlim(min(lo) - pad, max(lo) + pad); axm.set_ylim(min(la) - pad, max(la) + pad)
    axm.set_aspect(1 / np.cos(np.deg2rad(np.mean(la))))
    axm.set_facecolor("#f7f9fb"); axm.tick_params(labelsize=7)
    axm.set_xlabel("Longitude (°)", fontsize=8); axm.set_ylabel("Latitude (°)", fontsize=8)
    ttl = fig.suptitle("", fontsize=12, x=0.07, ha="left", fontweight="bold")
    # legend of levels
    for i, (n, c) in enumerate(LEVEL_COLORS.items()):
        fig.text(0.07 + i * 0.12, 0.935, f"■ {n}", color=c, fontsize=9, fontweight="bold")

    ser = fs["series"].dropna()
    ser = ser[(ser.index >= dates[0] - pd.Timedelta(days=1)) & (ser.index <= dates[-1] + pd.Timedelta(days=1))]
    ymax = float(max([ser.max() if len(ser) else 1] + [v for v in fs["th"].values() if v])) * 1.1
    bounds = [0, fs["th"].get("Jaune"), fs["th"].get("Orange"), fs["th"].get("Rouge"), ymax]
    for (n, c), lo_, hi_ in zip(LEVEL_COLORS.items(), bounds[:-1], bounds[1:]):
        if lo_ is not None and hi_ is not None and hi_ > lo_:
            axh.axhspan(lo_, hi_, color=c, alpha=0.10, lw=0)
    axh.plot(ser.index, ser.values, color=T.BLUE, lw=1.4)
    cur = axh.axvline(dates[0], color=T.INK, lw=0.8, ls=":")
    dot, = axh.plot([dates[0]], [np.nan], "o", color=T.INK, ms=6)
    axh.set_ylim(0, ymax); axh.set_xlim(dates[0] - pd.Timedelta(days=2), dates[-1] + pd.Timedelta(days=2))
    axh.set_ylabel(f"Débit ({unit})", fontsize=8); axh.tick_params(labelsize=7)
    axh.set_title(f"Hydrogramme – {fs['name']}", fontsize=9, loc="left")
    for a in (axh,):
        a.spines[["top", "right"]].set_visible(False)

    def draw(k):
        d = dates[k]
        for s, segs, sc, lab in zip(stations, lines, dots, labels):
            q = _value(s["series"], d)
            lv = level(q, s["th"]) if np.isfinite(q) else None
            col = LEVEL_COLORS[lv] if lv else "#9aa3ad"
            for g in segs:
                g.set_color(col); g.set_linewidth(_width(q, s["series"]) * 0.7)
            sc.set_color(col)
            lab.set_text(f"{s['name']}  {q:.1f} {unit}" if np.isfinite(q) else s["name"])
        cur.set_xdata([d, d])
        dot.set_data([d], [_value(fs["series"], d)])
        ttl.set_text(f"{title} — {d:%d/%m/%Y}")
        return []

    anim = FuncAnimation(fig, draw, frames=len(dates), blit=False)
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "anim.gif")
        anim.save(path, writer=PillowWriter(fps=fps))
        plt.close(fig)
        with open(path, "rb") as f:
            return f.read()
