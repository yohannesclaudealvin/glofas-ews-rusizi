import datetime as dt
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import streamlit as st

import forecast_batch
from app_state import (ROOT, add_station, chart, coords, embed_html, glofas_dict, num, obs_wide, page_setup,
                       performance, registry, thresholds)
from ews import theme as T
from ews.correction import ForecastArchive, operational_forecast
from ews.geo import fetch_rivers, map_html, match_river, station_map
from ews.glofas_api import fetch_forecast
from ews.glofas_netcdf import BURUNDI_BBOX, download_forecast, extract_point
from ews.plots import forecast_panel

page_setup("Prévision des inondations", icon="🚨")
ARCHIVE_FILE = ROOT / "archive" / "forecast_archive.csv"
TZ = ZoneInfo("Africa/Bujumbura")
NEW = "— nouvelle station —"


# ------------------------------------------------------------------ helpers
def log(msg: str, level: str = "INFO"):
    st.session_state.setdefault("fc_log", []).append(f"{dt.datetime.now(TZ):%Y-%m-%d %H:%M:%S} - {level} - {msg}")


@st.cache_data(ttl=3 * 3600, show_spinner=False)
def auto_forecast(lat, lon, days, day):
    return fetch_forecast(lat, lon, past_days=3, forecast_days=min(days + 1, 30), ensemble=True)


@st.cache_data(ttl=7 * 24 * 3600, show_spinner=False)
def rivers_near(lat, lon):
    return fetch_rivers(lat, lon, radius_m=15000)


def level(q, th):
    lv = "Vert"
    for n in ("Jaune", "Orange", "Rouge"):
        v = th.get(n)
        if v is not None and q is not None and np.isfinite(q) and q >= v:
            lv = n
    return lv


ICON = {"Vert": "🟢", "Jaune": "🟡", "Orange": "🟠", "Rouge": "🔴"}

if "fc_log" not in st.session_state:
    log("Bienvenue sur l'outil de visualisation des prévisions de GloFAS")
if "archive" not in st.session_state:
    st.session_state["archive"] = ForecastArchive(pd.read_csv(ARCHIVE_FILE)) if ARCHIVE_FILE.exists() else ForecastArchive()

tab1, tab2 = st.tabs(["Prévision d'une station", "Toutes les stations"])

# ==================================================================================== one station
with tab1:
    left, right = st.columns([1, 1.9], gap="large")

    # ---------------------------------------------------------------- zone 1: download
    with left:
        with st.container(border=True):
            st.markdown("**Télécharger**")
            source = st.radio("Source des prévisions GloFAS", key="one_source", options=["Automatique", "Copernicus (clé API)", "Fichier NetCDF"],
                              horizontal=True, label_visibility="collapsed",
                              help="Automatique : sans clé, la prévision est téléchargée au moment d'exécuter. "
                                   "Copernicus : fichier NetCDF officiel (clé du Early Warning Data Store). "
                                   "Fichier NetCDF : un fichier déjà téléchargé.")
            if source == "Copernicus (clé API)":
                key = st.text_input("Clé API Copernicus", type="password", placeholder="Entrez votre clé Copernicus")
                a, b = st.columns(2)
                lon_min = a.number_input("Longitude min", value=BURUNDI_BBOX["lon_min"], format="%.2f")
                lon_max = b.number_input("Longitude max", value=BURUNDI_BBOX["lon_max"], format="%.2f")
                lat_min = a.number_input("Latitude min", value=BURUNDI_BBOX["lat_min"], format="%.2f")
                lat_max = b.number_input("Latitude max", value=BURUNDI_BBOX["lat_max"], format="%.2f")
                a, b = st.columns([2, 1])
                nc_day = a.date_input("Date de la prévision", dt.datetime.now(TZ).date() - dt.timedelta(days=1),
                                      key="nc_day")
                b.write(""); b.write("")
                if b.button("OK", width="stretch", disabled=not key):
                    try:
                        with st.spinner("Téléchargement GloFAS depuis Copernicus (une à quelques minutes)…"):
                            nc = download_forecast(key, nc_day, dict(lon_min=lon_min, lon_max=lon_max,
                                                                     lat_min=lat_min, lat_max=lat_max), days=30)
                        st.session_state["nc"] = (nc, f"Copernicus {nc_day:%Y-%m-%d}")
                        log(f"Prévision GloFAS du {nc_day:%d/%m/%Y} téléchargée ({len(nc) / 1e6:.1f} Mo)")
                    except Exception as e:
                        log(f"Téléchargement Copernicus impossible : {e}", "ERREUR")
            elif source == "Fichier NetCDF":
                f = st.file_uploader("Fichier NetCDF GloFAS (.nc)", type=["nc", "nc4", "netcdf"])
                if f is not None and st.session_state.get("nc", (None, ""))[1] != f.name:
                    st.session_state["nc"] = (f.getvalue(), f.name)
                    log(f"Fichier {f.name} chargé")
            else:
                st.caption("La dernière prévision GloFAS (51 membres) est téléchargée automatiquement à l'exécution.")
            if source != "Automatique" and st.session_state.get("nc"):
                st.caption(f"Fichier en mémoire : {st.session_state['nc'][1]}")

        # ------------------------------------------------------------ zone 2: forecast parameters
        reg = registry()
        with st.container(border=True):
            st.markdown("**Prévision**")
            choice = st.selectbox("Station", list(sorted(reg)) + [NEW],
                                  index=sorted(reg).index(st.session_state["station"]) if st.session_state.get("station") in reg else 0)
            if choice == NEW:
                name = st.text_input("Nom de la station", placeholder="ex. GITEGA").strip().upper()
                river = st.text_input("Rivière", placeholder="ex. Ruvubu")
                c0 = (None, None)
            else:
                name, river = choice, reg[choice]["river"]
                c0 = coords(reg[choice]) or (None, None)
            a, b = st.columns(2)
            lon = a.number_input("Longitude", value=c0[1], format="%.4f", step=0.01, key=f"lon_{choice}")
            lat = b.number_input("Latitude", value=c0[0], format="%.4f", step=0.01, key=f"lat_{choice}")
            verify = st.toggle("Vérifier la position sur le cours d'eau", value=False)

            st.markdown("Seuils d'alerte (m³/s)")
            th0 = thresholds(obs_wide(), choice) if choice != NEW else {}
            d = {"Jaune": th0.get("Vigilance"), "Orange": th0.get("Alerte"), "Rouge": th0.get("Alerte maximale")}
            th = {}
            for n, colr in (("Rouge", "#d03b3b"), ("Orange", "#ec835a"), ("Jaune", "#fab219")):
                a, b = st.columns([1, 2])
                a.markdown(f"<div style='background:{colr};color:white;border-radius:4px;padding:6px 10px;"
                           f"margin-top:2px;font-weight:600'>{n}</div>", unsafe_allow_html=True)
                th[n] = num(b.number_input(n, value=num(d[n]), format="%.2f", label_visibility="collapsed",
                                           key=f"th_{n}_{choice}", placeholder="débit à partir duquel"))
            st.markdown("<div style='background:#0ca30c;color:white;border-radius:4px;padding:6px 10px;"
                        "font-weight:600'>Vert : en dessous du seuil jaune</div>", unsafe_allow_html=True)
            if choice != NEW and th0:
                st.caption("Valeurs proposées d'après l'historique : Q90, crue de 2 ans, crue de 5 ans.")

            a, b = st.columns([3, 2])
            q_obs = a.number_input("Observation du jour (m³/s)", min_value=0.0, value=None, format="%.2f",
                                   key=f"obs_{choice}", placeholder="débit observé")
            nbr = b.number_input("Nbr de jours", min_value=1, max_value=29, value=7, step=1)
            run_day = st.date_input("Date d'émission", dt.datetime.now(TZ).date(), key="one_day",
                                    disabled=source != "Automatique",
                                    help="Pour un fichier NetCDF, la date est celle du fichier.")
            run = st.button("EXÉCUTER", type="primary", width="stretch", key="one_run")

    # ---------------------------------------------------------------- run
    if run:
        try:
            if not name:
                raise ValueError("indiquez le nom de la station")
            if num(lat) is None or num(lon) is None:
                raise ValueError("indiquez la longitude et la latitude de la station")
            if q_obs is None:
                raise ValueError("indiquez l'observation du jour")
            if choice == NEW:
                add_station(name, river, lat, lon, lat, lon, select=False)
                log(f"Station {name} ajoutée ({lat:.4f}, {lon:.4f})")
            elif coords(reg[choice]) != (lat, lon):
                reg[choice]["cell_lat"], reg[choice]["cell_lon"] = float(lat), float(lon)
            if source == "Automatique":
                fc = auto_forecast(float(lat), float(lon), int(nbr), str(run_day))
                t0 = pd.Timestamp(run_day)
                log(f"Prévision GloFAS téléchargée pour {name} ({lat:.3f}, {lon:.3f})")
            else:
                if not st.session_state.get("nc"):
                    raise ValueError("aucun fichier NetCDF : téléchargez-le (OK) ou chargez un fichier")
                fc = extract_point(st.session_state["nc"][0], float(lat), float(lon))
                t0 = fc.index.min()
                cl = fc.attrs.get("cell")
                log(f"Maille GloFAS utilisée : {cl[0]:.3f}, {cl[1]:.3f} (fichier {st.session_state['nc'][1]})")
            if t0 not in fc.index:
                raise ValueError(f"la prévision ne contient pas la date {t0:%d/%m/%Y}")
            leads = list(range(1, int(nbr) + 1))
            arch = st.session_state["archive"]
            arch.add(name, t0, fc, leads)
            res = operational_forecast(fc, t0, float(q_obs), arch.df[arch.df["issue_date"] < t0], station=name,
                                       leads=leads)
            if len(res) < len(leads):
                log(f"La prévision ne couvre que {len(res)} jour(s) sur {len(leads)} demandés", "ATTENTION")
            res["niveau"] = [f"{ICON[level(v, th)]} {level(v, th)}" for v in res["corrected"]]
            worst = max((level(v, th) for v in res["corrected"]), key=["Vert", "Jaune", "Orange", "Rouge"].index)
            st.session_state["one_res"] = dict(name=name, res=res, q=float(q_obs), t0=t0, th=th)
            i = res["corrected"].idxmax()
            log(f"Prévision exécutée pour {name} : correction {res['error_added'].iloc[0]:+.2f} m³/s, "
                f"maximum corrigé {res.loc[i, 'corrected']:.2f} m³/s le {pd.Timestamp(res.loc[i, 'valid_date']):%d/%m}, "
                f"niveau {worst}")
            try:
                ARCHIVE_FILE.parent.mkdir(exist_ok=True); ARCHIVE_FILE.write_bytes(arch.to_csv())
            except Exception:
                pass
        except Exception as e:
            log(f"Prévision impossible : {e}", "ERREUR")

    # ---------------------------------------------------------------- zone 3: chart
    with right:
        with st.container(border=True):
            show = st.radio("Afficher", ["Corrigée", "Brute", "Les deux"], index=2, horizontal=True, key="one_show")
            out = st.session_state.get("one_res")
            if out:
                fig = forecast_panel(out["name"], out["res"], out["q"], out["t0"], out["th"], show)
                chart(fig, key="one_chart")
                a, b, c = st.columns(3)
                a.download_button("Télécharger le graphique (HTML)", fig.to_html(include_plotlyjs="cdn").encode(),
                                  f"prevision_{out['name']}_{out['t0']:%Y%m%d}.html", "text/html", width="stretch")
                cols = {"lead": "Échéance (j)", "valid_date": "Date", "glofas_raw": "GloFAS brut",
                        "corrected": "Prévision corrigée", "error_added": "Correction", "niveau": "Niveau",
                        "cor_min": "Ens. min", "cor_median": "Ens. médiane", "cor_max": "Ens. max", "method": "Méthode"}
                tab = out["res"][[c for c in cols if c in out["res"].columns]].rename(columns=cols)
                b.download_button("Télécharger les données (CSV)", tab.to_csv(index=False).encode(),
                                  f"prevision_{out['name']}_{out['t0']:%Y%m%d}.csv", "text/csv", width="stretch")
                c.download_button("Archive des prévisions (CSV)", st.session_state["archive"].to_csv(),
                                  "forecast_archive.csv", "text/csv", width="stretch")
                with st.expander("Tableau de la prévision"):
                    st.dataframe(tab.round(2), hide_index=True, width="stretch")
            else:
                st.markdown("<div style='height:380px;display:flex;align-items:center;justify-content:center;"
                            "color:#9aa3ad'>Le graphique de la prévision s'affichera ici.</div>",
                            unsafe_allow_html=True)

        if verify:
            with st.container(border=True):
                if num(lat) is None or num(lon) is None:
                    st.info("Indiquez d'abord la longitude et la latitude.")
                else:
                    ways = []
                    try:
                        ways = rivers_near(round(float(lat), 3), round(float(lon), 3))
                    except Exception as e:
                        log(f"Tracé des rivières indisponible : {e}", "ATTENTION")
                    found, rw = match_river(ways, river or "", name)
                    m = station_map(name or "Station", river or "", float(lat), float(lon), None, None,
                                    rw, [w for w in ways if w not in rw])
                    embed_html(map_html(m), 380)
                    st.caption(f"Rivière reconnue : {found}" if found else
                               "Rivière non reconnue par son nom : vérifiez que le point tombe bien sur le cours d'eau.")

        # ------------------------------------------------------------ zone 4: messages
        with st.container(border=True, height=170):
            st.markdown("**Messages**")
            for line in reversed(st.session_state.get("fc_log", [])[-30:]):
                colr = "#b2272f" if " ERREUR " in line else ("#a35a00" if " ATTENTION " in line else "#374151")
                st.markdown(f"<div style='font-family:monospace;font-size:0.82rem;color:{colr}'>{line}</div>",
                            unsafe_allow_html=True)

# ==================================================================================== all stations
with tab2:
    forecast_batch.render()
