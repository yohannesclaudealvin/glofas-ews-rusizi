import datetime as dt
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import streamlit as st

from app_state import ROOT, has_data, performance, sidebar_status, stations_config, thresholds
from ews.correction import ForecastArchive, operational_forecast
from ews.glofas_api import fetch_forecast
from ews.plots import forecast_chart

sidebar_status()
st.title("🚨 7 · Prévision corrigée à 7 jours")
st.markdown("1) Saisissez le **débit observé aujourd'hui** à chaque station ; 2) l'application télécharge la "
            "dernière prévision GloFAS (ensemble de 51 membres) ; 3) elle applique la correction en temps réel et "
            "donne la prévision corrigée pour les 7 prochains jours, avec les niveaux d'alerte.")

ARCHIVE_FILE = ROOT / "archive" / "forecast_archive.csv"


@st.cache_data(ttl=3 * 3600, show_spinner=False)
def get_fc(lat, lon, day):           # `day` makes the cache refresh every day
    return fetch_forecast(lat, lon, past_days=7, forecast_days=8, ensemble=True)


FR = {"lead": "Échéance (j)", "valid_date": "Date", "glofas_raw": "GloFAS brut", "error_added": "Correction",
      "method": "Méthode", "corrected": "Prévision corrigée", "cor_min": "Ens. min", "cor_p25": "Ens. p25",
      "cor_median": "Ens. médiane", "cor_p75": "Ens. p75", "cor_max": "Ens. max", "alert": "Alerte",
      "alert (ensemble max)": "Alerte (ens. max)", "reliability": "Fiabilité historique"}
ICON = {"Vigilance": "🟡 Vigilance", "Alerte": "🟠 Alerte", "Alerte maximale": "🔴 Alerte maximale"}


def alert_level(q, th: dict) -> str:
    """Highest level whose threshold is reached (thresholds need not be pre-sorted)."""
    if not th or q is None or not np.isfinite(q): return "—"
    lvl = "🟢 Normal"
    for name in ("Vigilance", "Alerte", "Alerte maximale"):
        v = th.get(name)
        if v is not None and np.isfinite(v) and q >= v:
            lvl = ICON[name]
    return lvl


def reliability(station: str, lead: int) -> str:
    if not has_data() or station not in st.session_state["glofas"]:
        return "non évaluée"
    try:
        p = performance(st.session_state["obs"], st.session_state["glofas"], station)
        v = p[(p["Series"] == "Corrected") & (p["Lead"] == lead)]["NSE"].iloc[0]
    except Exception:
        return "non évaluée"
    return "bonne" if v >= 0.5 else ("moyenne" if v >= 0 else "faible")


# ---------------------------------------------------------------- inputs
tz = ZoneInfo("Africa/Bujumbura")
c1, c2 = st.columns([1, 2])
today = c1.date_input("Date d'aujourd'hui (émission de la prévision)", dt.datetime.now(tz).date())
cfg = stations_config()
cfg_ok = cfg.dropna(subset=["lat", "lon"])
missing = cfg[cfg["lat"].isna() | cfg["lon"].isna()]["station"].tolist()
if missing:
    c2.info("Stations sans coordonnées de maille GloFAS (à définir dans *Configuration des stations*) : "
            + ", ".join(missing))

st.subheader("Débit observé aujourd'hui (m³/s)")
q_today = {}
cols = st.columns(3)
for i, s_ in enumerate(cfg_ok["station"].tolist()):
    q_today[s_] = cols[i % 3].number_input(s_, min_value=0.0, value=None, step=0.1, format="%.2f", key=f"q_{s_}",
                                           placeholder="débit observé")

with st.expander("Seuils d'alerte par station (modifiables)", expanded=False):
    st.markdown("Valeurs par défaut calculées sur les débits observés historiques : Q90, crue de 2 ans et crue de "
                "5 ans (Gumbel), classées par ordre croissant. Remplacez-les par les seuils officiels si vous en avez.")
    tkey = "thr_table"
    if tkey not in st.session_state or set(st.session_state[tkey]["Station"]) != set(cfg["station"]):
        o = st.session_state.get("obs")
        rows = []
        for s_ in cfg["station"]:
            th_ = thresholds(o, s_)
            rows.append({"Station": s_, **{k: th_.get(k, np.nan) for k in ("Vigilance", "Alerte", "Alerte maximale")}})
        st.session_state[tkey] = pd.DataFrame(rows)
    thr_tab = st.data_editor(st.session_state[tkey], hide_index=True, width="stretch",
                             column_config={"Station": st.column_config.TextColumn(disabled=True)})

with st.expander("Archive des prévisions (pour la formule de même échéance)"):
    st.markdown("Chaque jour, l'application ajoute la prévision GloFAS brute du jour à l'archive. Après L jours, "
                "l'archive contient la prévision à L jours valable aujourd'hui, et la formule de l'article "
                "(erreur de même échéance) est utilisée automatiquement. En ligne (Streamlit Cloud), le stockage "
                "n'est pas permanent : **téléchargez l'archive après chaque utilisation et rechargez-la ici**.")
    up = st.file_uploader("Charger l'archive (forecast_archive.csv)", type="csv")
    if up is not None:
        st.session_state["archive"] = ForecastArchive(pd.read_csv(up))
    elif "archive" not in st.session_state:
        st.session_state["archive"] = ForecastArchive(pd.read_csv(ARCHIVE_FILE)) if ARCHIVE_FILE.exists() else ForecastArchive()
    st.caption(f"{len(st.session_state['archive'].df)} prévisions dans l'archive.")

with st.expander("Importer une prévision GloFAS manuellement (sans internet)"):
    st.markdown("CSV avec les colonnes `date` et `river_discharge`, et éventuellement `river_discharge_min`, "
                "`_p25`, `_median`, `_p75`, `_max`. Le fichier doit contenir la date d'aujourd'hui et les 7 jours suivants.")
    man_st = st.selectbox("Station", cfg["station"].tolist(), key="man_st")
    man_f = st.file_uploader("Prévision (CSV)", type="csv", key="man_f")
    if man_f is not None:
        mf = pd.read_csv(man_f); mf["date"] = pd.to_datetime(mf["date"])
        st.session_state.setdefault("manual_fc", {})[man_st] = mf.set_index("date")
        st.success(f"Prévision importée pour {man_st}.")

run = st.button("Télécharger la prévision GloFAS et calculer la prévision corrigée", type="primary")

# ---------------------------------------------------------------- compute
if run:
    t0 = pd.Timestamp(today)
    results, summary, errors = {}, [], []
    arch = st.session_state["archive"]
    obs_hist = st.session_state.get("obs")
    manual = st.session_state.get("manual_fc", {})
    with st.spinner("Téléchargement des prévisions GloFAS…"):
        for _, r in cfg.iterrows():
            s = r["station"]
            q_obs = q_today.get(s)
            q_obs = float(q_obs) if q_obs is not None else None
            try:
                if s in manual:
                    fc = manual[s]
                elif pd.notna(r["lat"]) and pd.notna(r["lon"]):
                    fc = get_fc(float(r["lat"]), float(r["lon"]), str(today))
                else:
                    continue
            except Exception as e:
                errors.append(f"{s} : impossible de télécharger la prévision GloFAS (connexion internet ?) — {type(e).__name__}"); continue
            if t0 in fc.index:
                arch.add(s, t0, fc)
            if q_obs is None:
                errors.append(f"{s} : pas de débit observé saisi — prévision brute archivée seulement"); continue
            try:
                res = operational_forecast(fc, t0, q_obs, arch.df[arch.df["issue_date"] < t0], station=s)
            except Exception as e:
                errors.append(f"{s} : {e}"); continue
            trow = thr_tab[thr_tab["Station"] == s]
            th = {k: float(trow[k].iloc[0]) for k in ("Vigilance", "Alerte", "Alerte maximale")
                  if len(trow) and pd.notna(trow[k].iloc[0])}
            res["alert"] = [alert_level(v, th) for v in res["corrected"]]
            if "cor_max" in res:
                res["alert (ensemble max)"] = [alert_level(v, th) for v in res["cor_max"]]
            res["reliability"] = [reliability(s, L) for L in res["lead"]]
            results[s] = (fc, res, q_obs, th)
            imax = res["corrected"].idxmax()
            order = ["🟢 Normal", "🟡 Vigilance", "🟠 Alerte", "🔴 Alerte maximale"]
            worst = max(res["alert"], key=lambda a: order.index(a) if a in order else -1)
            summary.append({"Station": s, "Observé aujourd'hui (m³/s)": q_obs,
                            "GloFAS aujourd'hui (m³/s)": float(fc.loc[t0, "river_discharge"]),
                            "Correction appliquée (m³/s)": res["error_added"].iloc[0],
                            "Max corrigé 7 j (m³/s)": res.loc[imax, "corrected"],
                            "Date du max": res.loc[imax, "valid_date"], "Niveau d'alerte max": worst,
                            "Fiabilité historique (J+1 / J+7)": f"{res['reliability'].iloc[0]} / {res['reliability'].iloc[-1]}"})
    try:
        ARCHIVE_FILE.parent.mkdir(exist_ok=True); ARCHIVE_FILE.write_bytes(arch.to_csv())
    except Exception:
        pass
    st.session_state["op_results"] = (results, summary, errors, str(today))

# ---------------------------------------------------------------- display
if "op_results" in st.session_state:
    results, summary, errors, day = st.session_state["op_results"]
    for e in errors:
        st.warning(e)
    if summary:
        st.subheader(f"Synthèse du bassin – prévision émise le {day}")
        sm = pd.DataFrame(summary)
        st.dataframe(sm.round(2), width="stretch", hide_index=True)
        st.caption("Seuils : voir « Seuils d'alerte par station » (par défaut Q90, crue de 2 ans et crue de 5 ans, "
                   "classés par ordre croissant). Fiabilité = NSE "
                   "historique de la prévision corrigée (bonne ≥ 0,5 ; moyenne 0–0,5 ; faible < 0).")
        allres = []
        for s, (fc, res, q_obs, th) in results.items():
            with st.expander(f"{s} — {res['alert'].iloc[res['corrected'].values.argmax()]}", expanded=len(results) <= 3):
                st.plotly_chart(forecast_chart(s, None, res, q_obs, pd.Timestamp(day), th), width="stretch")
                st.dataframe(res.rename(columns=FR).round(2), width="stretch", hide_index=True)
            allres.append(res.assign(station=s, issue_date=day, obs_today=q_obs))
        out = pd.concat(allres)
        c1, c2 = st.columns(2)
        c1.download_button("Télécharger les prévisions corrigées (CSV)", out.to_csv(index=False).encode(),
                           f"prevision_corrigee_{day}.csv", "text/csv", type="primary")
    st.download_button("Télécharger l'archive mise à jour (forecast_archive.csv)", st.session_state["archive"].to_csv(),
                       "forecast_archive.csv", "text/csv")
