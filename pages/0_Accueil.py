import streamlit as st

from app_state import chart, meta_table, page_setup, registry
from ews.plots import basin_map_plotly

page_setup("Système d'alerte précoce GloFAS", icon="🌊")
st.markdown("""
<div class="hero"><h2>Bassin de la Rusizi – prévision des crues corrigée à 7 jours</h2>
<p>Méthodologie de l'article <i>Performance Assessment and Optimization of GloFAS Forecasts on the Rusizi River
Basin for Enhanced Anticipatory Flood Action</i>, appliquée station par station.</p></div>
""", unsafe_allow_html=True)

c1, c2, c3 = st.columns(3)
with c1:
    st.markdown("#### 1. Charger les stations")
    st.write("Pour chaque station : sa rivière, ses coordonnées, son fichier de débits observés et son fichier "
             "de prévisions GloFAS historiques.")
    st.page_link("pages/1_Stations.py", label="Charger les stations", icon="📂")
with c2:
    st.markdown("#### 2. Analyser")
    st.write("Fiche et carte de chaque station, correction en temps réel, performance (KGE, NSE…), qualité des "
             "prévisions, hydrogrammes, tendances et crues de référence.")
    st.page_link("pages/2_Fiche_station.py", label="Fiche station et carte", icon="📍")
with c3:
    st.markdown("#### 3. Prévoir")
    st.write("Saisissez le débit observé aujourd'hui : l'application télécharge GloFAS et donne la prévision "
             "corrigée des 7 prochains jours, avec les niveaux d'alerte.")
    st.page_link("pages/8_Prevision.py", label="Prévision à 7 jours", icon="🚨")

st.markdown("#### Formule de correction (section 2.3.2)")
st.latex(r"Q_{corr,L}(t) = Q_{GloFAS,L}(t) + \left[\,Q_{obs}(t-L) - Q_{GloFAS,L}(t-L)\,\right]")

if registry():
    st.markdown("#### Stations chargées")
    m = meta_table()
    if m["lat"].notna().any():
        chart(basin_map_plotly(m))
    st.dataframe(m, hide_index=True, width="stretch")
st.caption("GloFAS v4 : Copernicus Emergency Management Service, via l'API Open-Meteo Flood. "
           "Cours d'eau : © contributeurs OpenStreetMap.")
