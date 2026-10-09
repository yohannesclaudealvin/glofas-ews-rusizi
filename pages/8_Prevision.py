import datetime as dt
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import streamlit as st

from app_state import (ROOT, chart, glofas_dict, obs_wide, page_setup, performance, registry, thresholds)
from ews import theme as T
from ews.correction import ForecastArchive, operational_forecast
from ews.glofas_api import fetch_forecast
from ews.plots import forecast_chart

page_setup("Prévision corrigée à 7 jours", icon="🚨")
if not registry():
    st.warning("Aucune station chargée."); st.page_link("pages/1_Stations.py", label="Charger les stations"); st.stop()

ARCHIVE_FILE = ROOT / "archive" / "forecast_archive.csv"
FR = {"lead": "Échéance (j)", "valid_date": "Date", "glofas_raw": "GloFAS brut", "error_added": "Correction",
      "method": "Méthode", "corrected": "Prévision corrigée", "cor_min": "Ens. min", "cor_p25": "Ens. p25",
      "cor_median": "Ens. médiane", "cor_p75": "Ens. p75", "cor_max": "Ens. max", "alert": "Alerte",
      "alert (ensemble max)": "Alerte (ens. max)", "reliability": "Fiabilité historique"}
ORDER = ["Normal", "Vigilance", "Alerte", "Alerte maximale"]


@st.cache_data(ttl=3 * 3600, show_spinner=False)
def get_fc(lat, lon, day):                     # `day` refreshes the cache every day
    return fetch_forecast(lat, lon, past_days=7, forecast_days=8, ensemble=True)


def level(q, th: dict) -> str:
    if not th or q is None or not np.isfinite(q): return "—"
    lv = "Normal"
    for n in ORDER[1:]:
        v = th.get(n)
        if v is not None and np.isfinite(v) and q >= v: lv = n
    return lv


def label(lv: str) -> str:
    return f"{T.ICONS.get(lv, '')} {lv}" if lv in T.ICONS else lv


def reliability(station: str, lead: int) -> str:
    gl = glofas_dict()
    if station not in gl: return "non évaluée"
    try:
        p = performance(obs_wide(), gl, station)
        v = p[(p["Series"] == "Corrected") & (p["Lead"] == lead)]["NSE"].iloc[0]
    except Exception:
        return "non évaluée"
    return "bonne" if v >= 0.5 else ("moyenne" if v >= 0 else "faible")


reg = registry()
ready = [n for n, s in sorted(reg.items()) if (s["cell_lat"] or s["lat"]) is not None]
missing = [n for n in sorted(reg) if n not in ready]

tz = ZoneInfo("Africa/Bujumbura")
c1, c2 = st.columns([1, 2])
today = c1.date_input("Date d'émission (aujourd'hui)", dt.datetime.now(tz).date())
if missing:
    c2.info("Sans coordonnées (pas de prévision possible) : " + ", ".join(missing))

st.subheader("Débit observé aujourd'hui (m³/s)")
cols = st.columns(min(4, max(1, len(ready))))
q_today = {n: cols[i % len(cols)].number_input(f"{n} ({reg[n]['river']})", min_value=0.0, value=None, step=0.1,
                                                format="%.2f", key=f"q_{n}", placeholder="débit observé")
           for i, n in enumerate(ready)}

obs = obs_wide()
with st.expander("Seuils d'alerte par station (modifiables)"):
    st.caption("Par défaut : Q90, crue de 2 ans et crue de 5 ans. Remplacez-les par les seuils officiels si besoin.")
    if "thr_table" not in st.session_state or set(st.session_state["thr_table"]["Station"]) != set(ready):
        st.session_state["thr_table"] = pd.DataFrame(
            [{"Station": n, **{k: thresholds(obs, n).get(k, np.nan) for k in ORDER[1:]}} for n in ready])
    thr_tab = st.data_editor(st.session_state["thr_table"], hide_index=True, width="stretch",
                             column_config={"Station": st.column_config.TextColumn(disabled=True)})

with st.expander("Archive des prévisions"):
    st.caption("Téléchargez l'archive après chaque utilisation et rechargez-la la fois suivante.")
    up = st.file_uploader("Charger l'archive (forecast_archive.csv)", type="csv")
    if up is not None:
        st.session_state["archive"] = ForecastArchive(pd.read_csv(up))
    elif "archive" not in st.session_state:
        st.session_state["archive"] = (ForecastArchive(pd.read_csv(ARCHIVE_FILE)) if ARCHIVE_FILE.exists()
                                       else ForecastArchive())
    st.caption(f"{len(st.session_state['archive'].df)} prévisions dans l'archive.")

with st.expander("Importer une prévision GloFAS (sans internet)"):
    st.caption("CSV : `date`, `river_discharge` (+ facultatif `river_discharge_min`, `_p25`, `_median`, `_p75`, `_max`).")
    man_st = st.selectbox("Station", ready, key="man_st")
    man_f = st.file_uploader("Prévision (CSV)", type="csv", key="man_f")
    if man_f is not None:
        mf = pd.read_csv(man_f); mf["date"] = pd.to_datetime(mf["date"])
        st.session_state.setdefault("manual_fc", {})[man_st] = mf.set_index("date")
        st.success(f"Prévision importée pour {man_st}.")

if st.button("Télécharger GloFAS et calculer la prévision corrigée", type="primary"):
    t0 = pd.Timestamp(today)
    arch = st.session_state["archive"]
    manual = st.session_state.get("manual_fc", {})
    results, summary, msgs = {}, [], []
    with st.spinner("Téléchargement des prévisions GloFAS…"):
        for n in ready:
            s = reg[n]
            lat, lon = (s["cell_lat"], s["cell_lon"]) if s["cell_lat"] is not None else (s["lat"], s["lon"])
            try:
                fc = manual[n] if n in manual else get_fc(float(lat), float(lon), str(today))
            except Exception as e:
                msgs.append(f"{n} : prévision GloFAS indisponible (connexion internet ?) – {type(e).__name__}"); continue
            if t0 in fc.index:
                arch.add(n, t0, fc)
            q = q_today.get(n)
            if q is None:
                msgs.append(f"{n} : pas de débit observé saisi – prévision brute archivée seulement"); continue
            try:
                res = operational_forecast(fc, t0, float(q), arch.df[arch.df["issue_date"] < t0], station=n)
            except Exception as e:
                msgs.append(f"{n} : {e}"); continue
            tr = thr_tab[thr_tab["Station"] == n]
            th = {k: float(tr[k].iloc[0]) for k in ORDER[1:] if len(tr) and pd.notna(tr[k].iloc[0])}
            res["alert"] = [label(level(v, th)) for v in res["corrected"]]
            if "cor_max" in res:
                res["alert (ensemble max)"] = [label(level(v, th)) for v in res["cor_max"]]
            res["reliability"] = [reliability(n, L) for L in res["lead"]]
            worst = max((level(v, th) for v in res["corrected"]), key=lambda a: ORDER.index(a) if a in ORDER else -1)
            i = res["corrected"].idxmax()
            results[n] = (res, float(q), th)
            summary.append({"Station": n, "Rivière": s["river"], "Niveau max (7 j)": label(worst),
                            "Observé aujourd'hui": float(q), "GloFAS aujourd'hui": float(fc.loc[t0, "river_discharge"]),
                            "Correction": res["error_added"].iloc[0], "Max corrigé": res.loc[i, "corrected"],
                            "Date du max": res.loc[i, "valid_date"],
                            "Fiabilité J+1 / J+7": f"{res['reliability'].iloc[0]} / {res['reliability'].iloc[-1]}"})
    try:
        ARCHIVE_FILE.parent.mkdir(exist_ok=True); ARCHIVE_FILE.write_bytes(arch.to_csv())
    except Exception:
        pass
    st.session_state["op_results"] = (results, summary, msgs, str(today))

if "op_results" in st.session_state:
    results, summary, msgs, day = st.session_state["op_results"]
    for m in msgs:
        st.warning(m)
    if summary:
        st.subheader(f"Synthèse – prévision émise le {day}")
        sm = pd.DataFrame(summary)
        cols = st.columns(min(4, len(sm)))
        for i, r in sm.iterrows():
            cols[i % len(cols)].metric(r["Station"], f"{r['Max corrigé']:.1f} m³/s",
                                       delta=r["Niveau max (7 j)"], delta_color="off")
        st.dataframe(sm.round(2), width="stretch", hide_index=True)
        allres = []
        for n, (res, q, th) in results.items():
            with st.expander(f"{n} – {sm.set_index('Station').loc[n, 'Niveau max (7 j)']}", expanded=len(results) <= 2):
                chart(forecast_chart(n, res, q, pd.Timestamp(day), th), key=f"fc_{n}")
                st.dataframe(res.rename(columns=FR).round(2), width="stretch", hide_index=True)
            allres.append(res.assign(station=n, issue_date=day, obs_today=q))
        st.download_button("Télécharger les prévisions corrigées (CSV)", pd.concat(allres).to_csv(index=False).encode(),
                           f"prevision_corrigee_{day}.csv", "text/csv", type="primary")
    st.download_button("Télécharger l'archive mise à jour (forecast_archive.csv)", st.session_state["archive"].to_csv(),
                       "forecast_archive.csv", "text/csv")
