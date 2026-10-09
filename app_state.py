"""Shared state and cached computations for all pages."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

from ews import LEADS
from ews.correction import correct_station, performance_table
from ews.data_io import load_glofas, load_observations, load_sample, merge_station, qc_report
from ews.statistics import frequency_table

ROOT = Path(__file__).parent
SAMPLE_DIR = ROOT / "data" / "sample"
STATIONS_CSV = ROOT / "config" / "stations.csv"


# ---------------------------------------------------------------- data loading
def set_data(obs: pd.DataFrame, glofas: dict, source: str):
    st.session_state["obs"] = obs
    st.session_state["glofas"] = glofas
    st.session_state["source"] = source


def has_data() -> bool:
    return st.session_state.get("obs") is not None and bool(st.session_state.get("glofas"))


def require_data():
    if not has_data():
        st.warning("Aucune donnée chargée. Allez d'abord à la page **1 · Données** pour charger les "
                   "observations et les fichiers GloFAS.")
        st.page_link("pages/1_Donnees.py", label="Aller à la page Données", icon="📂")
        st.stop()
    return st.session_state["obs"], st.session_state["glofas"]


@st.cache_data(show_spinner=False)
def read_sample():
    return load_sample(SAMPLE_DIR)


@st.cache_data(show_spinner=False)
def read_uploads(obs_bytes: bytes, obs_name: str, gl_files: tuple):
    obs = load_observations(obs_bytes, obs_name)
    gl = {}
    for name, b in gl_files:
        stn, g = load_glofas(b, name)
        gl[stn] = g
    return obs, gl


def stations_config() -> pd.DataFrame:
    if "stations_cfg" not in st.session_state:
        st.session_state["stations_cfg"] = pd.read_csv(STATIONS_CSV)
    return st.session_state["stations_cfg"]


# ---------------------------------------------------------------- analyses
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
    tab, fits = frequency_table(obs[station], station, q_crit=q_crit, min_fraction=min_fraction)
    return tab


def thresholds(obs, station: str, q_crit: float = 0.9) -> dict:
    """Default alert thresholds from the historical record: Q90, Gumbel 2-yr and 5-yr floods,
    sorted by value and assigned to the three alert levels (lowest = Vigilance)."""
    if obs is None or station not in obs.columns or obs[station].dropna().empty:
        return {}
    t = frequency(obs, station, min_fraction=0.25, q_crit=q_crit)   # incomplete years excluded
    vals = sorted([float(t[f"Q{int(q_crit*100)} (alert)"].iloc[0]), float(t["Q2 Gumbel"].iloc[0]),
                   float(t["Q5 Gumbel"].iloc[0])])
    return dict(zip(LEVELS, vals))


LEVELS = ["Vigilance", "Alerte", "Alerte maximale"]


def sidebar_status():
    with st.sidebar:
        if has_data():
            obs, gl = st.session_state["obs"], st.session_state["glofas"]
            st.success(f"Données chargées ({st.session_state.get('source')}) : "
                       f"{len(gl)} stations GloFAS, {obs.shape[1]} stations observées.")
        else:
            st.info("Aucune donnée chargée.")
        st.caption("Méthode : correction en temps réel de GloFAS — "
                   "Q_corr,L(t) = Q_GloFAS,L(t) + [Q_obs(t−L) − Q_GloFAS,L(t−L)]")
