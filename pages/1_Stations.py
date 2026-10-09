import folium
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

from app_state import (SAMPLE_DIR, add_station, defaults, glofas_dict, load_sample, meta_table, num, obs_wide,
                       page_setup, qc, registry, remove_station, update_station)
from ews.data_io import load_glofas, load_station_observations
from ews.geo import propose_point, search_river

page_setup("Stations", icon="📂")

with st.expander("Format des fichiers"):
    c1, c2 = st.columns(2)
    c1.markdown("**Observations (une station)** – Excel ou CSV : 1ʳᵉ colonne = date, 2ᵉ colonne = débit (m³/s). "
                "Si le fichier contient plusieurs colonnes, vous choisirez la bonne.")
    c1.download_button("Modèle observations (CSV)", "Date,Q_m3s\n2024-01-01,152.3\n2024-01-04,149.8\n",
                       "modele_observations.csv", "text/csv")
    c2.markdown("**GloFAS historique (une station)** – Excel ou CSV : date, puis les prévisions aux échéances "
                "1 à 7 jours (8 colonnes).")
    c2.download_button("Modèle GloFAS (CSV)", "Date,LT_1J,LT_2J,LT_3J,LT_4J,LT_5J,LT_6J,LT_7J\n"
                       "2024-01-01,401.2,402.1,399.8,398.0,396.9,395.1,392.8\n", "modele_glofas.csv", "text/csv")

# ------------------------------------------------------------------ add a station
st.subheader("➕ Ajouter ou mettre à jour une station")
st.caption("N'importe quelle station du Burundi : choisissez-la dans la liste ou créez-en une nouvelle. "
           "Le fichier de débits observés est facultatif : sans lui, la station sert seulement à la prévision.")
d = defaults()
NEWST = "— nouvelle station —"
known = st.selectbox("Station connue (pré-remplit rivière et coordonnées)", [NEWST] + list(d["station"]),
                     key="known_station")
row = d[d["station"] == known].iloc[0] if known in set(d["station"]) else None
val = lambda k, default=None: (row[k] if row is not None and pd.notna(row[k]) else default)
if st.session_state.get("_known_prev") != known:          # new choice: refill the inputs
    st.session_state["_known_prev"] = known
    st.session_state["f_name"] = known if row is not None else ""
    st.session_state["f_river"] = val("river", "")
    for k, c in (("f_lat", "lat"), ("f_lon", "lon"), ("f_clat", "cell_lat"), ("f_clon", "cell_lon")):
        st.session_state[k] = num(val(c))
    st.session_state.pop("river_search", None)
if row is not None and isinstance(val("notes"), str) and val("notes"):
    st.caption(f"ℹ️ {val('notes')}")

a1, a2 = st.columns(2)
a1.text_input("Nom de la station", key="f_name", placeholder="ex. MUGERE")
a2.text_input("Rivière", key="f_river", placeholder="ex. Mugere")

# ---- locate the river in OpenStreetMap and pick the position on the map
with st.expander("🔎 Trouver la rivière et placer la station sur la carte", expanded=row is None):
    c1, c2 = st.columns([3, 1])
    c1.caption("Recherche du cours d'eau par son nom dans OpenStreetMap (Burundi). L'application propose un point "
               "à 3 km en amont de l'exutoire ; cliquez sur la carte pour placer la station exactement.")
    if c2.button("Chercher la rivière", width="stretch", disabled=not st.session_state.get("f_river")):
        try:
            with st.spinner("Recherche dans OpenStreetMap…"):
                ways = search_river(st.session_state["f_river"])
            st.session_state["river_search"] = ways
            if ways:
                pp = propose_point(ways)
                if num(st.session_state.get("f_lat")) is None:
                    st.session_state["f_lat"], st.session_state["f_lon"] = pp[0], pp[1]
                st.session_state["river_outlet"] = pp[2]
            else:
                st.warning("Aucun cours d'eau de ce nom au Burundi dans OpenStreetMap. Essayez une autre orthographe, "
                           "ou cliquez directement sur la carte.")
        except Exception as e:
            st.error(str(e))
    ways = st.session_state.get("river_search") or []
    clat, clon = num(st.session_state.get("f_lat")), num(st.session_state.get("f_lon"))
    center = [clat, clon] if clat is not None else ([ways[0]["coords"][0][0], ways[0]["coords"][0][1]] if ways
                                                    else [-3.38, 29.90])
    fm = folium.Map(location=center, zoom_start=11 if (clat is not None or ways) else 8, tiles=None)
    folium.TileLayer("OpenStreetMap", name="OpenStreetMap").add_to(fm)
    folium.TileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
                     attr="Esri", name="Satellite (Esri)", show=False).add_to(fm)
    for w in ways:
        folium.PolyLine(w["coords"], color="#1c5cab", weight=4, tooltip=w["name"]).add_to(fm)
    if ways:
        fm.fit_bounds([[min(c[0] for w in ways for c in w["coords"]), min(c[1] for w in ways for c in w["coords"])],
                       [max(c[0] for w in ways for c in w["coords"]), max(c[1] for w in ways for c in w["coords"])]])
    if st.session_state.get("river_outlet") and ways:
        folium.CircleMarker(st.session_state["river_outlet"], radius=5, color="#eb6834", fill=True,
                            tooltip="Exutoire").add_to(fm)
    if clat is not None and clon is not None:
        folium.Marker([clat, clon], tooltip=f"Station : {clat:.4f}, {clon:.4f}",
                      icon=folium.Icon(color="darkblue", icon="tint", prefix="fa")).add_to(fm)
    folium.LayerControl().add_to(fm)
    out = st_folium(fm, height=420, width=None, key="pick_map", returned_objects=["last_clicked"])
    click = (out or {}).get("last_clicked")
    if click and (round(click["lat"], 4), round(click["lng"], 4)) != st.session_state.get("_last_click"):
        st.session_state["_last_click"] = (round(click["lat"], 4), round(click["lng"], 4))
        st.session_state["f_lat"], st.session_state["f_lon"] = round(click["lat"], 4), round(click["lng"], 4)
        st.rerun()

with st.form("add_station", clear_on_submit=False):
    b1, b2, b3, b4 = st.columns(4)
    b1.number_input("Latitude station (°)", key="f_lat", format="%.5f", step=0.001)
    b2.number_input("Longitude station (°)", key="f_lon", format="%.5f", step=0.001)
    b3.number_input("Latitude maille GloFAS", key="f_clat", format="%.3f", step=0.05,
                    help="Centre de la maille GloFAS 0,05° utilisée pour la prévision. Laissez vide pour "
                         "utiliser les coordonnées de la station.")
    b4.number_input("Longitude maille GloFAS", key="f_clon", format="%.3f", step=0.05)
    f1, f2 = st.columns(2)
    obs_f = f1.file_uploader("Débits observés de la station (facultatif)", type=["xlsx", "xls", "csv"])
    gl_f = f2.file_uploader("Prévisions GloFAS historiques de la station (facultatif)", type=["xlsx", "xls", "csv"])
    submitted = st.form_submit_button("Enregistrer la station", type="primary")

if submitted:
    name, river = st.session_state["f_name"].strip(), st.session_state["f_river"]
    lat, lon = num(st.session_state["f_lat"]), num(st.session_state["f_lon"])
    clat_, clon_ = num(st.session_state["f_clat"]), num(st.session_state["f_clon"])
    if not name:
        st.error("Indiquez au moins le nom de la station.")
    elif obs_f is None:
        if lat is None or lon is None:
            st.error("Sans fichier de débits, il faut au moins les coordonnées de la station (pour la prévision).")
        else:
            gl = load_glofas(gl_f.getvalue(), gl_f.name)[1] if gl_f is not None else None
            add_station(name, river, lat, lon, clat_ if clat_ is not None else lat,
                        clon_ if clon_ is not None else lon, None, gl)
            st.success(f"Station {name.upper()} ajoutée sans observations : elle est disponible dans la page "
                       "8 · Prévision. Ajoutez ses débits observés plus tard pour les analyses.")
    else:
        try:
            obs, cols = load_station_observations(obs_f.getvalue(), obs_f.name)
            st.session_state["_pending"] = dict(name=name, river=river, lat=lat, lon=lon,
                                                clat=clat_ if clat_ is not None else lat,
                                                clon=clon_ if clon_ is not None else lon,
                                                obs_bytes=obs_f.getvalue(), obs_name=obs_f.name, cols=cols,
                                                gl=(gl_f.name, gl_f.getvalue()) if gl_f is not None else None)
        except Exception as e:
            st.error(f"Lecture des observations impossible : {e}")

p = st.session_state.get("_pending")
if p:
    col = p["cols"][0]
    if len(p["cols"]) > 1:
        col = st.selectbox(f"Le fichier contient plusieurs colonnes : laquelle correspond à {p['name'].upper()} ?",
                           p["cols"], index=next((i for i, c in enumerate(p["cols"]) if c.upper() == p["name"].upper()), 0))
    if len(p["cols"]) == 1 or st.button("Confirmer la colonne", type="primary"):
        try:
            obs, _ = load_station_observations(p["obs_bytes"], p["obs_name"], column=col)
            gl = load_glofas(p["gl"][1], p["gl"][0])[1] if p["gl"] else None
            add_station(p["name"], p["river"], p["lat"], p["lon"], p["clat"], p["clon"], obs, gl)
            st.session_state.pop("_pending")
            st.success(f"Station {p['name'].upper()} enregistrée ({len(obs)} observations"
                       f"{', GloFAS ' + str(len(gl)) + ' dates' if gl is not None else ''}).")
            st.rerun()
        except Exception as e:
            st.error(f"Erreur : {e}")

if SAMPLE_DIR.exists() and any(SAMPLE_DIR.iterdir()):
    st.caption("Données d'exemple disponibles : 9 stations IGEBU du bassin de la Rusizi (2008–2023).")
    if st.button("Charger les 9 stations d'exemple"):
        load_sample()
        st.rerun()

# ------------------------------------------------------------------ loaded stations
if registry():
    st.subheader("Stations chargées")
    m = meta_table()
    edited = st.data_editor(m, hide_index=True, width="stretch", key="meta_editor",
                            disabled=["station", "obs_start", "obs_end", "obs_n", "glofas"],
                            column_config={"lat": st.column_config.NumberColumn("lat station", format="%.5f"),
                                           "lon": st.column_config.NumberColumn("lon station", format="%.5f"),
                                           "cell_lat": st.column_config.NumberColumn("lat maille", format="%.3f"),
                                           "cell_lon": st.column_config.NumberColumn("lon maille", format="%.3f"),
                                           "river": "rivière", "obs_n": "n obs.", "glofas": "GloFAS"})
    c1, c2, c3 = st.columns([1, 1, 2])
    if c1.button("Enregistrer les modifications"):
        for _, r in edited.iterrows():
            update_station(r["station"], river=r["river"], lat=r["lat"], lon=r["lon"], cell_lat=r["cell_lat"],
                           cell_lon=r["cell_lon"])
        st.success("Coordonnées mises à jour.")
    c2.download_button("Télécharger stations.csv", edited.drop(columns=["obs_start", "obs_end", "obs_n", "glofas"])
                       .assign(notes="").to_csv(index=False).encode(), "stations.csv", "text/csv",
                       help="Remplacez config/stations.csv dans le dépôt GitHub pour garder ces coordonnées.")
    with c3:
        rm = st.selectbox("Retirer une station", ["—"] + list(m["station"]), label_visibility="collapsed")
        if rm != "—" and st.button(f"Retirer {rm}"):
            remove_station(rm); st.rerun()

    gl = glofas_dict()
    if gl:
        st.subheader("Contrôle qualité")
        rep = qc(obs_wide(), gl)
        st.dataframe(rep[rep["GloFAS file"] == "yes"].drop(columns=["GloFAS file"]), hide_index=True, width="stretch")
        bad = rep[rep["Flags"].str.contains("ratio", na=False)]
        if len(bad):
            st.warning("Pour " + ", ".join(bad["Station"]) + ", la moyenne GloFAS est très différente de la moyenne "
                       "observée : la maille GloFAS ne correspond probablement pas à la rivière de la station. "
                       "Vérifiez-la dans **2 · Fiche station et carte** (recherche de maille).")
    st.page_link("pages/2_Fiche_station.py", label="Voir la fiche et la carte de la station", icon="📍")
