"""GloFAS EWS – Rusizi basin. Streamlit entry point.

Run locally:  streamlit run app.py
"""
import streamlit as st

st.set_page_config(page_title="GloFAS EWS – Bassin de la Rusizi", page_icon="🌊", layout="wide")

pages = {
    "Préparation": [
        st.Page("pages/0_Accueil.py", title="Accueil", icon="🏠", default=True),
        st.Page("pages/1_Donnees.py", title="1 · Données", icon="📂"),
        st.Page("pages/8_Configuration.py", title="Configuration des stations", icon="📍"),
    ],
    "Analyses (méthodologie)": [
        st.Page("pages/2_Bassin.py", title="2 · Synthèse du bassin", icon="🗺️"),
        st.Page("pages/3_Performance.py", title="3 · Correction et performance", icon="📈"),
        st.Page("pages/4_Qualite_prevision.py", title="4 · Qualité des prévisions", icon="🎯"),
        st.Page("pages/5_Similarite.py", title="5 · Similarité des hydrogrammes", icon="〰️"),
        st.Page("pages/6_Frequences.py", title="6 · Tendances, fréquences, jours critiques", icon="📊"),
    ],
    "Opérationnel": [
        st.Page("pages/7_Prevision.py", title="7 · Prévision à 7 jours", icon="🚨"),
    ],
}
st.navigation(pages).run()
