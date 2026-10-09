import datetime as dt
from zoneinfo import ZoneInfo

import folium
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from streamlit_folium import st_folium

import forecast_batch
from app_state import ROOT, add_station, chart, coords, num, obs_wide, page_setup, registry, thresholds
from ews import theme as T
from ews.animation import animated_figure
from ews.correction import ForecastArchive, operational_forecast
from ews.geo import fetch_rivers, match_river
from ews.glofas_api import fetch_forecast
from ews.glofas_netcdf import ZONES, configured_key, download_forecast, extract_point
from ews.plots import forecast_panel

page_setup("Prévision des inondations", icon="🚨")
ARCHIVE_FILE = ROOT / "archive" / "forecast_archive.csv"
TZ = ZoneInfo("Africa/Bujumbura")
NEW = "— nouvelle station —"
ICON = {"Vert": "🟢", "Jaune": "🟡", "Orange": "🟠", "Rouge": "🔴"}
SOURCES = ["Automatique", "Copernicus (clé API)", "Fichier NetCDF"]


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


def raw_chart(raw):
    fc, t0 = raw["fc"], raw["t0"]
    f = fc[fc.index >= t0 - pd.Timedelta(days=3)]
    fig = go.Figure()
    if {"river_discharge_min", "river_discharge_max"} <= set(f.columns):
        x = list(f.index)
        fig.add_trace(go.Scatter(x=x + x[::-1], y=list(f["river_discharge_max"]) + list(f["river_discharge_min"][::-1]),
                                 fill="toself", fillcolor="rgba(154,163,173,0.18)", line=dict(width=0),
                                 name="Ensemble GloFAS (min–max)", hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=f.index, y=f["river_discharge"], name="GloFAS brut (contrôle)", mode="lines+markers",
                             line=dict(color=T.RAW, width=2, dash="dot")))
    fig.add_vline(x=t0, line=dict(color=T.INK, width=1, dash="dash"))
    fig.update_layout(title=f"{raw['name']} – GloFAS brut téléchargé ({raw['label']})", height=420,
                      yaxis_title="Débit (m³/s)", hovermode="x unified",
                      legend=dict(orientation="h", yanchor="top", y=-0.15, x=0))
    return fig


def get_raw(source, name, lat, lon, nbr, run_day):
    """Download (or read) the GloFAS forecast for the station cell. Returns the 'raw' record."""
    if source == "Automatique":
        log(f"Connexion à GloFAS (API Open-Meteo) pour {name} ({lat:.4f}, {lon:.4f})…")
        fc = auto_forecast(float(lat), float(lon), int(nbr), str(run_day))
        t0, label = pd.Timestamp(run_day), f"prévision du {run_day:%d/%m/%Y}, Open-Meteo"
        cell = (lat, lon)
    else:
        if not st.session_state.get("nc"):
            raise ValueError("aucun fichier NetCDF : cliquez sur OK pour le télécharger depuis Copernicus, "
                             "ou chargez un fichier")
        fc = extract_point(st.session_state["nc"][0], float(lat), float(lon))
        t0, label = fc.index.min(), f"fichier {st.session_state['nc'][1]}"
        cell = fc.attrs.get("cell", (lat, lon))
    if t0 not in fc.index:
        raise ValueError(f"la prévision GloFAS ne contient pas la date {t0:%d/%m/%Y}")
    fut = fc[fc.index > t0]
    nmem = "51 membres" if "river_discharge_max" in fc.columns else "contrôle seul"
    log(f"GloFAS reçu : {label}, {len(fut)} jour(s) de prévision (du {fut.index.min():%d/%m} au "
        f"{fut.index.max():%d/%m}), {nmem}, maille {cell[0]:.3f}, {cell[1]:.3f} ; "
        f"débit GloFAS du jour {float(fc.loc[t0, 'river_discharge']):.2f} m³/s")
    return dict(fc=fc, t0=t0, label=label, name=name, lat=float(lat), lon=float(lon), source=source,
                day=str(run_day))


if "fc_log" not in st.session_state:
    log("Bienvenue sur l'outil de visualisation des prévisions de GloFAS")
if "archive" not in st.session_state:
    st.session_state["archive"] = ForecastArchive(pd.read_csv(ARCHIVE_FILE)) if ARCHIVE_FILE.exists() else ForecastArchive()
# a click on the verification map sets the coordinates before the inputs are drawn
if "pending_xy" in st.session_state:
    ch, la_, lo_ = st.session_state.pop("pending_xy")
    st.session_state[f"lat_{ch}"], st.session_state[f"lon_{ch}"] = la_, lo_

tab1, tab2 = st.tabs(["Prévision d'une station", "Toutes les stations"])

# ==================================================================================== one station
with tab1:
    left, right = st.columns([1, 1.9], gap="large")
    reg = registry()

    # ---------------------------------------------------------------- zone 1: download
    with left:
        with st.container(border=True):
            st.markdown("**Télécharger**")
            source = st.radio("Source des prévisions GloFAS", SOURCES, horizontal=True, key="one_source",
                              label_visibility="collapsed",
                              help="Automatique : sans clé, par l'API Open-Meteo (GloFAS v4). Copernicus : fichier "
                                   "NetCDF officiel du Early Warning Data Store (clé API). Fichier NetCDF : un fichier "
                                   "déjà téléchargé.")
            dl = False
            if source == "Automatique":
                st.caption("La dernière prévision GloFAS (contrôle + 50 membres) est téléchargée pour les coordonnées "
                           "de la station, sans clé. Vous pouvez la voir avant de saisir l'observation.")
                dl = st.button("Télécharger la prévision GloFAS", width="stretch", key="one_dl")
            elif source == "Copernicus (clé API)":
                k0 = configured_key(st.secrets if hasattr(st, "secrets") else None)
                key = st.text_input("Clé API Copernicus", type="password", value=k0 or "",
                                    placeholder="Entrez votre clé Copernicus (EWDS)",
                                    help="Clé personnelle (API Token) du compte ewds.climate.copernicus.eu. Elle peut "
                                         "être configurée une fois pour toutes dans les secrets de l'application "
                                         "(CDS_API_KEY) ou dans le fichier ~/.cdsapirc.")
                if k0:
                    st.caption("✔️ Clé configurée dans le système.")
                zone = st.selectbox("Zone (bassin)", list(ZONES) + ["Autour de la station", "Personnalisée"],
                                    key="one_zone")
                bb = dict(ZONES.get(zone, ZONES["Burundi entier"]))
                if zone == "Autour de la station":
                    cs = reg.get(st.session_state.get("one_station") or st.session_state.get("station") or "")
                    xy = coords(cs) if cs else None
                    if xy:
                        bb = {"lat_min": round(xy[0] - 0.3, 2), "lat_max": round(xy[0] + 0.3, 2),
                              "lon_min": round(xy[1] - 0.3, 2), "lon_max": round(xy[1] + 0.3, 2)}
                a, b = st.columns(2)
                lon_min = a.number_input("Longitude min", value=bb["lon_min"], format="%.2f", key=f"lonmin_{zone}")
                lon_max = b.number_input("Longitude max", value=bb["lon_max"], format="%.2f", key=f"lonmax_{zone}")
                lat_min = a.number_input("Latitude min", value=bb["lat_min"], format="%.2f", key=f"latmin_{zone}")
                lat_max = b.number_input("Latitude max", value=bb["lat_max"], format="%.2f", key=f"latmax_{zone}")
                a, b = st.columns([2, 1])
                nc_day = a.date_input("Date de la prévision", dt.datetime.now(TZ).date() - dt.timedelta(days=1),
                                      key="nc_day", help="GloFAS est publié chaque jour vers midi (UTC) ; la "
                                                         "prévision de la veille est toujours disponible.")
                b.write(""); b.write("")
                cop_ok = b.button("OK", width="stretch", disabled=not key, key="cop_ok")
            else:
                f = st.file_uploader("Fichier GloFAS (.nc ou .zip)", type=["nc", "nc4", "netcdf", "zip"])
                if f is not None and st.session_state.get("nc", (None, ""))[1] != f.name:
                    st.session_state["nc"] = (f.getvalue(), f.name)
                    log(f"Fichier {f.name} chargé ({len(f.getvalue()) / 1e6:.1f} Mo)")
            if source != "Automatique" and st.session_state.get("nc"):
                st.caption(f"Fichier en mémoire : {st.session_state['nc'][1]}")

        # ------------------------------------------------------------ zone 2: forecast parameters
        with st.container(border=True):
            st.markdown("**Prévision**")
            names = list(sorted(reg))
            choice = st.selectbox("Station", names + [NEW],
                                  index=names.index(st.session_state["station"])
                                  if st.session_state.get("station") in reg else 0, key="one_station")
            if choice == NEW:
                name = st.text_input("Nom de la station", placeholder="ex. MUGERE").strip().upper()
                river = st.text_input("Rivière", placeholder="ex. Mugere")
                c0 = (None, None)
            else:
                name, river = choice, reg[choice]["river"]
                c0 = coords(reg[choice]) or (None, None)
            a, b = st.columns(2)
            lon = a.number_input("Longitude", value=c0[1], format="%.4f", step=0.01, key=f"lon_{choice}")
            lat = b.number_input("Latitude", value=c0[0], format="%.4f", step=0.01, key=f"lat_{choice}")
            verify = st.toggle("Vérifier la position sur le cours d'eau", value=False, key="one_verify")

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
            elif not th0:
                st.caption("Pas d'historique pour cette station : saisissez les seuils (sinon tout reste vert).")

            a, b = st.columns([3, 2])
            q_obs = a.number_input("Observation du jour (m³/s)", min_value=0.0, value=None, format="%.2f",
                                   key=f"obs_{choice}", placeholder="débit observé")
            nbr = b.number_input("Nbr de jours", min_value=1, max_value=29, value=7, step=1, key="one_nbr")
            run_day = st.date_input("Date d'émission", dt.datetime.now(TZ).date(), key="one_day",
                                    disabled=source != "Automatique",
                                    help="Pour un fichier NetCDF, la date est celle du fichier.")
            run = st.button("EXÉCUTER", type="primary", width="stretch", key="one_run")

    # ---------------------------------------------------------------- actions
    if source == "Copernicus (clé API)" and cop_ok:
        try:
            log(f"Requête Copernicus EWDS : prévision du {nc_day:%d/%m/%Y}, zone {lat_min:.2f}/{lat_max:.2f} N, "
                f"{lon_min:.2f}/{lon_max:.2f} E…")
            with st.spinner("Téléchargement GloFAS depuis Copernicus (une à quelques minutes)…"):
                nc = download_forecast(key, nc_day, dict(lon_min=lon_min, lon_max=lon_max, lat_min=lat_min,
                                                         lat_max=lat_max), days=30)
            st.session_state["nc"] = (nc, f"Copernicus {nc_day:%Y-%m-%d}")
            log(f"Prévision GloFAS du {nc_day:%d/%m/%Y} téléchargée ({len(nc) / 1e6:.1f} Mo)")
        except Exception as e:
            msg = str(e)
            if "licen" in msg.lower() or "403" in msg:
                msg += " — acceptez la licence du jeu « GloFAS forecasts » sur ewds.climate.copernicus.eu"
            log(f"Téléchargement Copernicus impossible : {msg}", "ERREUR")

    if dl:
        try:
            if num(lat) is None or num(lon) is None:
                raise ValueError("indiquez d'abord la longitude et la latitude de la station")
            st.session_state["raw"] = get_raw(source, name or "Station", lat, lon, nbr, run_day)
            st.session_state.pop("one_res", None)
        except Exception as e:
            log(f"Téléchargement GloFAS impossible : {e}. Essayez la source Copernicus ou un fichier NetCDF.",
                "ERREUR")

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
            raw = st.session_state.get("raw")
            if not (raw and raw["name"] == name and raw["lat"] == float(lat) and raw["lon"] == float(lon)
                    and raw["source"] == source and (source != "Automatique" or raw["day"] == str(run_day))):
                raw = get_raw(source, name, lat, lon, nbr, run_day)
                st.session_state["raw"] = raw
            fc, t0 = raw["fc"], raw["t0"]
            leads = list(range(1, int(nbr) + 1))
            arch = st.session_state["archive"]
            past = arch.df[arch.df["issue_date"] < t0]
            arch.add(name, t0, fc, leads)
            res = operational_forecast(fc, t0, float(q_obs), past, station=name, leads=leads)
            if len(res) < len(leads):
                log(f"La prévision ne couvre que {len(res)} jour(s) sur {len(leads)} demandés", "ATTENTION")
            res["niveau"] = [f"{ICON[level(v, th)]} {level(v, th)}" for v in res["corrected"]]
            worst = max((level(v, th) for v in res["corrected"]), key=["Vert", "Jaune", "Orange", "Rouge"].index)
            st.session_state["one_res"] = dict(name=name, river=river, lat=float(lat), lon=float(lon), res=res,
                                               q=float(q_obs), t0=t0, th=th,
                                               q_glofas_t0=float(fc.loc[t0, "river_discharge"]))
            i = res["corrected"].idxmax()
            log(f"Correction : Qobs({t0:%d/%m}) {float(q_obs):.2f} − GloFAS({t0:%d/%m}) "
                f"{float(fc.loc[t0, 'river_discharge']):.2f} = {res['error_added'].iloc[0]:+.2f} m³/s ajoutés à "
                f"chaque échéance ({res['method'].iloc[0]})")
            log(f"Prévision exécutée pour {name} : maximum corrigé {res.loc[i, 'corrected']:.2f} m³/s le "
                f"{pd.Timestamp(res.loc[i, 'valid_date']):%d/%m}, niveau {worst}")
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
            raw = st.session_state.get("raw")
            if out:
                fig = forecast_panel(out["name"], out["res"], out["q"], out["t0"], out["th"], show)
                chart(fig, key="one_chart")
                a, b, c = st.columns(3)
                a.download_button("Télécharger le graphique (HTML)", fig.to_html(include_plotlyjs="cdn").encode(),
                                  f"prevision_{out['name']}_{out['t0']:%Y%m%d}.html", "text/html", width="stretch")
                cols = {"lead": "Échéance (j)", "valid_date": "Date", "glofas_raw": "GloFAS brut",
                        "error_added": "Correction", "corrected": "Prévision corrigée", "niveau": "Niveau",
                        "cor_min": "Ens. min", "cor_median": "Ens. médiane", "cor_max": "Ens. max", "method": "Méthode"}
                tab = out["res"][[c for c in cols if c in out["res"].columns]].rename(columns=cols)
                b.download_button("Télécharger les données (CSV)", tab.to_csv(index=False).encode(),
                                  f"prevision_{out['name']}_{out['t0']:%Y%m%d}.csv", "text/csv", width="stretch")
                c.download_button("Archive des prévisions (CSV)", st.session_state["archive"].to_csv(),
                                  "forecast_archive.csv", "text/csv", width="stretch")
                with st.expander("🧮 Détail du calcul de la correction"):
                    r0 = out["res"].iloc[0]
                    qg = out["q"] - r0["error_added"]
                    st.markdown(
                        f"La correction utilise **la prévision GloFAS téléchargée** et **l'observation du jour** :\n\n"
                        f"- débit observé aujourd'hui : Q<sub>obs</sub>(t₀) = **{out['q']:.2f}** m³/s\n"
                        f"- débit GloFAS pour aujourd'hui : Q<sub>GloFAS</sub>(t₀) = **{qg:.2f}** m³/s "
                        f"({r0['method']})\n"
                        f"- erreur de GloFAS aujourd'hui : {out['q']:.2f} − {qg:.2f} = **{r0['error_added']:+.2f}** m³/s\n\n"
                        "Cette erreur est ajoutée à la prévision GloFAS de chaque échéance : "
                        "Q<sub>corr</sub>(t₀+L) = Q<sub>GloFAS</sub>(t₀+L) + [Q<sub>obs</sub>(t₀) − Q<sub>GloFAS</sub>(t₀)].",
                        unsafe_allow_html=True)
                    det = out["res"][["lead", "valid_date", "glofas_raw", "error_added", "corrected", "niveau"]].copy()
                    det.columns = ["Échéance (j)", "Date", "GloFAS brut", "+ erreur", "= prévision corrigée", "Niveau"]
                    st.dataframe(det.round(2), hide_index=True, width="stretch")
                with st.expander("🎞️ Carte animée de la prévision"):
                    try:
                        ways = rivers_near(round(out["lat"], 3), round(out["lon"], 3))
                    except Exception as e:
                        ways = []
                        st.caption(f"Tracé des rivières indisponible : {e}")
                    _, rw = match_river(ways, out.get("river") or "", out["name"])
                    r = out["res"]
                    ser = pd.concat([pd.Series([out["q"]], index=[pd.Timestamp(out["t0"])]),
                                     pd.Series(r["corrected"].values, index=pd.to_datetime(r["valid_date"]))])
                    stn = [dict(name=out["name"], river=out.get("river"), lat=out["lat"], lon=out["lon"], ways=rw,
                                series=ser, th={k: v for k, v in out["th"].items() if v is not None})]
                    afig = animated_figure(stn, list(ser.index), title=f"Prévision corrigée {out['name']}",
                                           other_ways=[w for w in ways if w not in rw], height=640)
                    chart(afig, key="one_anim")
                    st.download_button("⬇️ Animation (HTML)", afig.to_html(include_plotlyjs="cdn").encode(),
                                       f"animation_prevision_{out['name']}.html", "text/html")
            elif raw:
                fig = raw_chart(raw)
                chart(fig, key="raw_chart")
                st.info("Prévision GloFAS brute téléchargée. Saisissez l'observation du jour puis cliquez sur "
                        "EXÉCUTER pour obtenir la prévision corrigée.")
                rr = raw["fc"][raw["fc"].index >= raw["t0"]].round(2)
                st.download_button("Télécharger GloFAS brut (CSV)", rr.to_csv().encode(),
                                   f"glofas_brut_{raw['name']}_{raw['t0']:%Y%m%d}.csv", "text/csv")
                with st.expander("Tableau GloFAS brut"):
                    st.dataframe(rr, width="stretch")
            else:
                st.markdown("<div style='height:380px;display:flex;align-items:center;justify-content:center;"
                            "color:#9aa3ad;text-align:center'>1. Téléchargez la prévision GloFAS<br>"
                            "2. Saisissez l'observation du jour<br>3. EXÉCUTER</div>", unsafe_allow_html=True)

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
                    fm = folium.Map(location=[float(lat), float(lon)], zoom_start=13, tiles=None)
                    folium.TileLayer("OpenStreetMap", name="OpenStreetMap").add_to(fm)
                    folium.TileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/"
                                     "tile/{z}/{y}/{x}", attr="Esri", name="Satellite (Esri)", show=False).add_to(fm)
                    for w in ways:
                        folium.PolyLine(w["coords"], color="#1c5cab" if w in rw else "#86b6ef",
                                        weight=4 if w in rw else 1.5, tooltip=w["name"]).add_to(fm)
                    h = 0.025
                    cla, clo = round((float(lat) + h) / 0.05) * 0.05 - h, round((float(lon) - h) / 0.05) * 0.05 + h
                    folium.Rectangle([[cla - h, clo - h], [cla + h, clo + h]], color="#eb6834", weight=2,
                                     fill=True, fill_opacity=0.06, tooltip="Maille GloFAS 0,05°").add_to(fm)
                    folium.Marker([float(lat), float(lon)], tooltip=f"{name} : {float(lat):.4f}, {float(lon):.4f}",
                                  icon=folium.Icon(color="darkblue", icon="tint", prefix="fa")).add_to(fm)
                    folium.LayerControl().add_to(fm)
                    o = st_folium(fm, height=380, width=None, key="verify_map", returned_objects=["last_clicked"])
                    st.caption((f"Rivière reconnue : {found}. " if found else
                                "Rivière non reconnue par son nom. ") +
                               "Cliquez sur la carte pour déplacer la station sur le cours d'eau.")
                    clk = (o or {}).get("last_clicked")
                    if clk and (round(clk["lat"], 4), round(clk["lng"], 4)) != st.session_state.get("_vclick"):
                        st.session_state["_vclick"] = (round(clk["lat"], 4), round(clk["lng"], 4))
                        st.session_state["pending_xy"] = (choice, round(clk["lat"], 4), round(clk["lng"], 4))
                        log(f"Position modifiée sur la carte : {clk['lat']:.4f}, {clk['lng']:.4f}")
                        st.rerun()

        # ------------------------------------------------------------ zone 4: messages
        with st.container(border=True, height=190):
            st.markdown("**Messages**")
            for line in reversed(st.session_state.get("fc_log", [])[-40:]):
                colr = "#b2272f" if " ERREUR " in line else ("#a35a00" if " ATTENTION " in line else "#374151")
                st.markdown(f"<div style='font-family:monospace;font-size:0.82rem;color:{colr}'>{line}</div>",
                            unsafe_allow_html=True)

# ==================================================================================== all stations
with tab2:
    forecast_batch.render()
