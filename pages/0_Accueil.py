import streamlit as st

from app_state import SAMPLE_DIR, chart, load_sample, meta_table, page_setup, registry
from ews.plots import basin_map_plotly

page_setup("Système d'alerte précoce GloFAS", icon="🌊")
st.markdown("""
<div class="hero"><h2>Prévision des crues corrigée à 7 jours – bassin de la Rusizi</h2>
<p>Prévisions GloFAS corrigées avec les débits observés aux stations.</p></div>
""", unsafe_allow_html=True)

if not registry():
    c1, c2 = st.columns([1, 2])
    if c1.button("Essayer avec les données d'exemple", type="primary", disabled=not (SAMPLE_DIR.exists() and any(SAMPLE_DIR.iterdir()))):
        load_sample()
        st.rerun()
    c2.caption("9 stations du bassin de la Rusizi (2008–2023). Vous pourrez ensuite charger vos propres stations.")

c1, c2, c3 = st.columns(3)
c1.page_link("pages/1_Stations.py", label="1. Charger les stations", icon="📂")
c2.page_link("pages/2_Fiche_station.py", label="2. Voir la fiche et la carte", icon="📍")
c3.page_link("pages/8_Prevision.py", label="3. Faire la prévision du jour", icon="🚨")
st.caption("Première utilisation ? Lisez le guide : il explique chaque page et chaque méthode.")
st.page_link("pages/9_Guide.py", label="Guide et méthodes", icon="📘")

if registry():
    st.markdown("#### Stations chargées")
    m = meta_table()
    if m["lat"].notna().any():
        chart(basin_map_plotly(m))
    st.dataframe(m, hide_index=True, width="stretch")
st.caption("GloFAS v4 : Copernicus Emergency Management Service, via l'API Open-Meteo Flood. "
           "Cours d'eau : © contributeurs OpenStreetMap.")
