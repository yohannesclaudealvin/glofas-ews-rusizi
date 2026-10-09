import pandas as pd
import streamlit as st

from app_state import has_data, sidebar_status, stations_config
from ews.glofas_api import find_cell

sidebar_status()
st.title("📍 Configuration des stations")
st.markdown("Coordonnées de la **maille GloFAS** (0,05°) utilisée pour chaque station dans la prévision "
            "opérationnelle. Les trois stations de l'article sont déjà configurées. Pour une nouvelle station, "
            "utilisez l'outil de recherche ci-dessous, puis **téléchargez le fichier `stations.csv`** et remplacez "
            "`config/stations.csv` dans votre dépôt GitHub pour que la configuration soit permanente.")

cfg = stations_config()
new = st.data_editor(cfg, num_rows="dynamic", width="stretch", hide_index=True,
                     column_config={"lat": st.column_config.NumberColumn(format="%.3f"),
                                    "lon": st.column_config.NumberColumn(format="%.3f")})
c1, c2 = st.columns(2)
if c1.button("Enregistrer pour cette session", type="primary"):
    new["station"] = new["station"].astype(str).str.upper()
    st.session_state["stations_cfg"] = new
    st.success("Configuration enregistrée pour cette session.")
c2.download_button("Télécharger stations.csv", new.to_csv(index=False).encode(), "stations.csv", "text/csv")

st.divider()
st.subheader("🔎 Recherche de la maille GloFAS d'une station")
st.markdown("Donnez la position approximative de la station. L'outil compare les mailles voisines (rayon de "
            "3 mailles, environ 15 km) à une série de référence : la prévision GloFAS historique à 1 jour du fichier "
            "chargé (recommandé, pour retrouver la maille utilisée), ou les débits observés (pour trouver la maille "
            "qui ressemble le plus à la rivière). Score = corrélation des moyennes mensuelles − |log(rapport des moyennes)|.")
if not has_data():
    st.info("Chargez d'abord les données (page 1) pour disposer d'une série de référence.")
    st.stop()
obs, gl = st.session_state["obs"], st.session_state["glofas"]
c1, c2, c3, c4 = st.columns(4)
s = c1.selectbox("Station", sorted(set(gl) | set(obs.columns)))
lat = c2.number_input("Latitude approx.", value=-3.30, format="%.3f", step=0.01)
lon = c3.number_input("Longitude approx.", value=29.30, format="%.3f", step=0.01)
ref_kind = c4.radio("Référence", ["GloFAS historique (1 j)", "Débits observés"])
if st.button("Chercher"):
    ref = gl[s]["LT_1J"] if (ref_kind.startswith("GloFAS") and s in gl) else obs[s]
    try:
        with st.spinner("Interrogation de GloFAS (≈ 1 minute)…"):
            res = find_cell(lat, lon, ref)
        st.dataframe(res.head(10).round(3), width="stretch", hide_index=True)
        best = res.iloc[0]
        st.success(f"Maille proposée : lat {best.cell_lat}, lon {best.cell_lon} "
                   f"(corrélation {best.corr_monthly:.2f}, rapport des moyennes {best.mean_ratio:.2f}). "
                   "Vérifiez sur une carte qu'elle est bien sur la rivière, puis reportez-la dans le tableau ci-dessus.")
    except Exception as e:
        st.error(f"Échec de la requête : {e}")
