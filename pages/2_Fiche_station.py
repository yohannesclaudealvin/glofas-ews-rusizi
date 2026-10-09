import streamlit as st

from app_state import chart, current_station, embed_html, page_setup, registry
from ews.geo import fetch_rivers, geojson, map_html, match_river, station_map
from ews.glofas_api import find_cell
from ews.plots import obs_series

page_setup("Fiche station et carte", icon="📍")
if not registry():
    st.warning("Aucune station chargée.")
    st.page_link("pages/1_Stations.py", label="Charger les stations", icon="📂")
    st.stop()

name = current_station()
s = registry()[name]
obs = s["obs"]
st.markdown(f"""<div class="hero"><h2>Station {name}</h2><p>Rivière {s['river']} · bassin de la Rusizi</p></div>""",
            unsafe_allow_html=True)

c = st.columns(5)
c[0].metric("Latitude", f"{s['lat']:.4f}°" if s["lat"] is not None else "—")
c[1].metric("Longitude", f"{s['lon']:.4f}°" if s["lon"] is not None else "—")
c[2].metric("Période observée", f"{obs.index.min():%Y}–{obs.index.max():%Y}")
c[3].metric("Débit moyen", f"{obs.mean():.2f} m³/s")
c[4].metric("Débit max observé", f"{obs.max():.1f} m³/s")
if s["cell_lat"] is not None:
    st.caption(f"Maille GloFAS utilisée pour la prévision : {s['cell_lat']:.3f}°, {s['cell_lon']:.3f}° (0,05° ≈ 5,5 km). "
               "Coordonnées modifiables dans la page 1 · Stations.")

# ------------------------------------------------------------------ map
st.subheader("🗺️ Carte de la rivière")
if s["lat"] is None or s["lon"] is None:
    st.info("Coordonnées de la station non renseignées : complétez-les dans la page 1 · Stations pour afficher la carte.")
else:
    @st.cache_data(ttl=7 * 24 * 3600, show_spinner=False)
    def rivers(lat, lon):
        return fetch_rivers(lat, lon, radius_m=30000)

    ways, err = [], None
    with st.spinner("Tracé des cours d'eau (OpenStreetMap)…"):
        try:
            ways = rivers(round(s["lat"], 3), round(s["lon"], 3))
        except Exception as e:
            err = str(e)
    found, river_ways = match_river(ways, s["river"], name)
    c1, c2 = st.columns([3, 1])
    show_others = c2.toggle("Afficher les autres cours d'eau", value=False)
    others = [{"station": n, "river": v["river"], "lat": v["lat"], "lon": v["lon"]}
              for n, v in registry().items() if n != name and v["lat"] is not None]
    m = station_map(name, s["river"], s["lat"], s["lon"], s["cell_lat"], s["cell_lon"], river_ways,
                    [w for w in ways if w not in river_ways] if show_others else None, others)
    html = map_html(m)
    with c1:
        embed_html(html, 560)
    with c2:
        if err:
            st.warning(f"Tracé des rivières indisponible : {err}")
        elif found:
            st.success(f"Rivière trouvée dans OpenStreetMap : **{found}** ({len(river_ways)} tronçons).")
        else:
            st.info(f"La rivière « {s['river']} » n'a pas été trouvée dans OpenStreetMap autour de la station. "
                    "Activez « autres cours d'eau » pour voir le réseau.")
        st.markdown("**Légende**  \n🔵 station · 🟧 maille GloFAS  \n━ rivière de la station  \n⚪ autres stations")
        st.download_button("⬇️ Carte interactive (HTML)", html.encode("utf-8"), f"carte_{name}.html", "text/html",
                           type="primary", width="stretch")
        st.download_button("⬇️ Géométries (GeoJSON)",
                           geojson(name, s["river"], s["lat"], s["lon"], s["cell_lat"], s["cell_lon"], river_ways),
                           f"{name}.geojson", "application/geo+json", width="stretch")
        st.caption("Le fichier HTML s'ouvre dans n'importe quel navigateur (fonds de carte : OSM, relief, satellite). "
                   "Le GeoJSON s'ouvre dans QGIS / ArcGIS.")

# ------------------------------------------------------------------ observed series
st.subheader("Débits observés")
chart(obs_series(obs, f"{name} – débit observé"))

# ------------------------------------------------------------------ GloFAS cell finder
with st.expander("🔎 Rechercher la bonne maille GloFAS pour cette station"):
    st.markdown("Compare les mailles GloFAS voisines (rayon de 3 mailles ≈ 15 km) avec une série de référence. "
                "Score = corrélation des moyennes mensuelles − |log(rapport des moyennes)|.")
    ref_kind = st.radio("Référence", ["Débits observés", "GloFAS historique (1 j)"], horizontal=True,
                        disabled=s["glofas"] is None)
    if st.button("Chercher la maille", disabled=s["lat"] is None):
        ref = s["glofas"]["LT_1J"] if (ref_kind.startswith("GloFAS") and s["glofas"] is not None) else obs
        try:
            with st.spinner("Interrogation de GloFAS (≈ 1 minute)…"):
                st.session_state.setdefault("cell_res", {})[name] = find_cell(s["lat"], s["lon"], ref)
        except Exception as e:
            st.error(f"Échec de la requête : {e}")
    res = st.session_state.get("cell_res", {}).get(name)
    if res is not None and len(res):
        st.dataframe(res.head(10).round(3), hide_index=True, width="stretch")
        b = res.iloc[0]
        st.success(f"Maille proposée : {b.cell_lat}, {b.cell_lon} (corrélation {b.corr_monthly:.2f}, "
                   f"rapport des moyennes {b.mean_ratio:.2f}).")
        if st.button("Utiliser cette maille pour la prévision"):
            s["cell_lat"], s["cell_lon"] = float(b.cell_lat), float(b.cell_lon)
            st.rerun()
