"""GloFAS EWS – Rusizi basin. Streamlit entry point.

Run locally:  streamlit run app.py
"""
import streamlit as st

st.set_page_config(page_title="GloFAS EWS – Bassin de la Rusizi", page_icon="🌊", layout="wide")

pages = {
    "Démarrer": [
        st.Page("pages/0_Accueil.py", title="Accueil", icon="🏠", default=True),
        st.Page("pages/1_Stations.py", title="1 · Stations (chargement)", icon="📂"),
        st.Page("pages/2_Fiche_station.py", title="2 · Fiche station et carte", icon="📍"),
    ],
    "Analyses": [
        st.Page("pages/3_Bassin.py", title="3 · Synthèse du bassin", icon="🗺️"),
        st.Page("pages/4_Performance.py", title="4 · Correction et performance", icon="📈"),
        st.Page("pages/5_Qualite_prevision.py", title="5 · Qualité des prévisions", icon="🎯"),
        st.Page("pages/6_Similarite.py", title="6 · Hydrogrammes", icon="〰️"),
        st.Page("pages/7_Frequences.py", title="7 · Tendances et crues", icon="📊"),
    ],
    "Opérationnel": [
        st.Page("pages/8_Prevision.py", title="8 · Prévision à 7 jours", icon="🚨"),
    ],
}
st.navigation(pages).run()
