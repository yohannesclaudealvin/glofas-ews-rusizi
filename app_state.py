"""Station registry, cached computations and page helpers shared by all pages."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

from ews import theme
from ews.correction import correct_station, performance_table
from ews.data_io import load_glofas, load_station_observations, merge_station, qc_report
from ews.statistics import frequency_table

ROOT = Path(__file__).parent
SAMPLE_DIR = ROOT / "data" / "sample" / "stations"
STATIONS_CSV = ROOT / "config" / "stations.csv"
LEVELS = ["Vigilance", "Alerte", "Alerte maximale"]


# ======================================================================= page setup
def page_setup(title: str, subtitle: str | None = None, icon: str = ""):
    st.markdown(theme.APP_CSS, unsafe_allow_html=True)
    sidebar()
    st.title(f"{icon} {title}".strip())
    if subtitle:
        st.caption(subtitle)


def sidebar():
    with st.sidebar:
        names = station_names()
        if names:
            cur = st.session_state.get("station")
            idx = names.index(cur) if cur in names else 0
            st.session_state["station"] = st.selectbox("Station active", names, index=idx, key="_station_select")
            st.caption(f"{len(names)} station(s) chargée(s)")
        else:
            st.info("Aucune station chargée.")


def embed_html(html: str, height: int = 560):
    """Embed a self-generated HTML page (the Folium map). st.iframe on recent Streamlit, components.html before."""
    if hasattr(st, "iframe"):
        st.iframe(html, height=height)
    else:
        import streamlit.components.v1 as components
        components.html(html, height=height)


def chart(fig, key: str | None = None):
    st.plotly_chart(fig, width="stretch", config=theme.PLOTLY_CONFIG, key=key)


# ======================================================================= station registry
def defaults() -> pd.DataFrame:
    return pd.read_csv(STATIONS_CSV)


def registry() -> dict:
    return st.session_state.setdefault("stations", {})


def station_names() -> list[str]:
    return sorted(registry())


def num(v):
    """Float or None (None, '', NaN and non-numbers all become None)."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if np.isfinite(f) else None


def coords(s: dict):
    """(lat, lon) of the GloFAS cell used for the forecast: the cell if set, else the station."""
    if num(s.get("cell_lat")) is not None and num(s.get("cell_lon")) is not None:
        return num(s["cell_lat"]), num(s["cell_lon"])
    if num(s.get("lat")) is not None and num(s.get("lon")) is not None:
        return num(s["lat"]), num(s["lon"])
    return None


def add_station(name: str, river: str, lat, lon, cell_lat, cell_lon, obs: pd.Series | None = None,
                glofas: pd.DataFrame | None = None, select: bool = True):
    name = str(name).strip().upper()
    if not name:
        return
    if obs is None:
        obs = pd.Series(dtype=float, index=pd.DatetimeIndex([]), name="Q")
    river = str(river).strip() if river is not None and str(river) != "nan" else ""
    registry()[name] = {"river": river or name.title(), "lat": num(lat), "lon": num(lon),
                        "cell_lat": num(cell_lat), "cell_lon": num(cell_lon), "obs": obs, "glofas": glofas}
    if select:
        st.session_state["station"] = name
    st.session_state.pop("op_results", None)


def remove_station(name: str):
    registry().pop(name, None)
    st.session_state.pop("op_results", None)


def meta_table() -> pd.DataFrame:
    rows = []
    for n, s in sorted(registry().items()):
        o = s["obs"]
        rows.append({"station": n, "river": s["river"], "lat": s["lat"], "lon": s["lon"],
                     "cell_lat": s["cell_lat"], "cell_lon": s["cell_lon"],
                     "obs_start": o.index.min().date() if len(o) else None,
                     "obs_end": o.index.max().date() if len(o) else None, "obs_n": len(o),
                     "glofas": "oui" if s["glofas"] is not None else "non"})
    return pd.DataFrame(rows)


def obs_wide() -> pd.DataFrame | None:
    reg = {n: s for n, s in registry().items() if len(s["obs"])}
    if not reg:
        return pd.DataFrame()
    return pd.concat({n: s["obs"] for n, s in reg.items()}, axis=1).sort_index()


def glofas_dict() -> dict:
    return {n: s["glofas"] for n, s in registry().items() if s["glofas"] is not None}


def require_stations(need_glofas: bool = True):
    if not registry() or (need_glofas and not glofas_dict()):
        st.warning("Aucune station avec données GloFAS n'est chargée. Commencez par la page **1 · Stations**.")
        st.page_link("pages/1_Stations.py", label="Charger les stations", icon="📂")
        st.stop()
    return obs_wide(), glofas_dict()


def current_station(require_glofas: bool = False) -> str:
    names = [n for n in station_names() if (not require_glofas or registry()[n]["glofas"] is not None)]
    if not names:
        require_stations(require_glofas)
    cur = st.session_state.get("station")
    return cur if cur in names else names[0]


# ======================================================================= sample data
@st.cache_data(show_spinner=False)
def _read_sample():
    out = {}
    for f in sorted(SAMPLE_DIR.glob("*_observations.csv")):
        st_ = f.name.split("_")[0].upper()
        obs, _ = load_station_observations(f, f.name)
        g = SAMPLE_DIR / f"{st_}_glofas.xlsx"
        out[st_] = (obs, load_glofas(g, g.name)[1] if g.exists() else None)
    return out


def load_sample():
    d = defaults().set_index("station")
    for st_, (obs, gl) in _read_sample().items():
        r = d.loc[st_] if st_ in d.index else pd.Series(dtype=object)
        add_station(st_, str(r.get("river", st_.title())), r.get("lat"), r.get("lon"), r.get("cell_lat"),
                    r.get("cell_lon"), obs, gl)


# ======================================================================= cached analyses
@st.cache_data(show_spinner=False)
def qc(obs, glofas):
    return qc_report(obs, glofas)


def usable_stations(obs, glofas) -> list[str]:
    q = qc(obs, glofas)
    return list(q.loc[q["Usable"], "Station"])


@st.cache_data(show_spinner=False)
def corrected(obs, glofas, station: str) -> pd.DataFrame:
    return correct_station(merge_station(obs, glofas[station], station))


@st.cache_data(show_spinner=False)
def performance(obs, glofas, station: str) -> pd.DataFrame:
    return performance_table(corrected(obs, glofas, station), station)


@st.cache_data(show_spinner=False)
def basin_performance(obs, glofas, stations: tuple) -> pd.DataFrame:
    return pd.concat([performance(obs, glofas, s) for s in stations], ignore_index=True)


@st.cache_data(show_spinner=False)
def frequency(obs, station: str, min_fraction: float = 0.0, q_crit: float = 0.9):
    tab, _ = frequency_table(obs[station], station, q_crit=q_crit, min_fraction=min_fraction)
    return tab


def thresholds(obs, station: str, q_crit: float = 0.9) -> dict:
    """Default alert thresholds: Q90, Gumbel 2-yr and 5-yr floods, sorted (lowest = Vigilance)."""
    if obs is None or station not in obs.columns or obs[station].dropna().size < 30:
        return {}
    t = frequency(obs, station, min_fraction=0.25, q_crit=q_crit)
    vals = sorted([float(t[f"Q{int(q_crit*100)} (alert)"].iloc[0]), float(t["Q2 Gumbel"].iloc[0]),
                   float(t["Q5 Gumbel"].iloc[0])])
    return dict(zip(LEVELS, vals))


def update_station(name: str, **kw):
    s = registry().get(name)
    if s is None:
        return
    for k, v in kw.items():
        s[k] = num(v) if k in ("lat", "lon", "cell_lat", "cell_lon") else v
