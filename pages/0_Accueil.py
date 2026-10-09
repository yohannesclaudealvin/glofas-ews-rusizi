import streamlit as st

from app_state import sidebar_status

sidebar_status()
st.title("🌊 Système d'alerte précoce GloFAS – Bassin de la Rusizi")
st.markdown(
    """
Cette application applique la méthodologie de l'article *Performance Assessment and Optimization of GloFAS
Forecasts on the Rusizi River Basin for Enhanced Anticipatory Flood Action* à **toutes les stations du bassin**.

**Étapes**

1. **Données** – chargez le fichier des débits observés (toutes les stations) et les fichiers de prévisions
   GloFAS historiques (un par station, échéances 1 à 7 jours). Un contrôle qualité est fait automatiquement.
2. **Analyses** – la correction en temps réel est appliquée, puis l'application calcule :
   - les critères de performance KGE, NSE, PBIAS et RSR par échéance (brut, corrigé, persistance) ;
   - la qualité des prévisions d'événements (POD, FAR, LR, ROC, CSI) ;
   - les hydrogrammes observé / brut / corrigé ;
   - les tendances (Mann-Kendall modifié), l'analyse fréquentielle (Gumbel, GEV, Normale) et les jours critiques.
3. **Prévision à 7 jours** – l'application télécharge la dernière prévision GloFAS (avec l'ensemble).
   Vous saisissez le débit observé aujourd'hui, et elle calcule la prévision corrigée pour les 7 prochains
   jours avec les niveaux d'alerte.

**Formule de correction (section 2.3.2)**
""")
st.latex(r"Q_{corr,L}(t) = Q_{GloFAS,L}(t) + \left[\,Q_{obs}(t-L) - Q_{GloFAS,L}(t-L)\,\right]")
st.markdown(
    """
En opérationnel (prévision émise aujourd'hui *t₀*, valable à *t₀ + L*) :
""")
st.latex(r"Q_{corr}(t_0+L) = Q_{GloFAS,L}(t_0+L) + \left[\,Q_{obs}(t_0) - Q_{GloFAS,L}(t_0)\,\right]")
st.markdown(
    """
*Q_GloFAS,L(t₀)* est la prévision à L jours émise il y a L jours pour aujourd'hui. Elle est lue dans l'**archive des
prévisions** que l'application constitue jour après jour. Si elle n'existe pas encore, l'erreur sur la valeur
GloFAS du jour est utilisée.

Données GloFAS v4 : Copernicus Emergency Management Service, via l'API Open-Meteo Flood.
""")
st.page_link("pages/1_Donnees.py", label="Commencer : charger les données", icon="📂")
