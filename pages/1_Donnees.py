import streamlit as st

from app_state import SAMPLE_DIR, qc, read_sample, read_uploads, set_data, sidebar_status, has_data

sidebar_status()
st.title("📂 1 · Données")

st.markdown("""
**Format attendu**
- **Observations** : un fichier Excel/CSV. 1ʳᵉ colonne = date, puis une colonne par station (débit en m³/s),
  avec le nom de la station en en-tête (ex. `RUSIZI`, `KABURANTWA` …).
- **GloFAS historique** : un fichier par station, 8 colonnes = date, puis les prévisions aux échéances 1 à 7 jours.
  La 2ᵉ colonne peut porter le nom de la station (comme dans les fichiers IGEBU) ; sinon, le nom du fichier
  (`Station_Glofas.xlsx`) est utilisé.
""")

c1, c2 = st.columns(2)
with c1:
    st.subheader("Charger vos fichiers")
    obs_f = st.file_uploader("Observations (toutes les stations)", type=["xlsx", "xls", "csv"])
    gl_fs = st.file_uploader("Prévisions GloFAS historiques (un fichier par station)", type=["xlsx", "xls", "csv"],
                             accept_multiple_files=True)
    if st.button("Charger ces fichiers", type="primary", disabled=not (obs_f and gl_fs)):
        try:
            obs, gl = read_uploads(obs_f.getvalue(), obs_f.name, tuple((f.name, f.getvalue()) for f in gl_fs))
            set_data(obs, gl, "fichiers chargés")
            st.success(f"{len(gl)} fichiers GloFAS chargés.")
        except Exception as e:
            st.error(f"Lecture impossible : {e}")
with c2:
    st.subheader("Ou utiliser les données d'exemple")
    if SAMPLE_DIR.exists() and any(SAMPLE_DIR.iterdir()):
        st.caption("Données IGEBU / GloFAS 2008–2023 du bassin de la Rusizi (9 stations).")
        if st.button("Charger les données d'exemple"):
            obs, gl = read_sample()
            set_data(obs, gl, "exemple")
            st.success("Données d'exemple chargées.")
    else:
        st.caption("Aucune donnée d'exemple dans data/sample.")

if has_data():
    obs, gl = st.session_state["obs"], st.session_state["glofas"]
    st.subheader("Inventaire et contrôle qualité")
    rep = qc(obs, gl)
    st.dataframe(rep, width="stretch", hide_index=True)
    bad = rep[rep["Flags"].str.contains("ratio", na=False)]
    if len(bad):
        st.warning(
            "Pour " + ", ".join(bad["Station"]) + ", la moyenne GloFAS est très différente de la moyenne observée. "
            "La maille GloFAS ne correspond probablement pas à la rivière de la station. La correction en temps "
            "réel reste applicable, mais il faut vérifier la maille dans **Configuration des stations** "
            "(outil de recherche de maille).")
    st.page_link("pages/2_Bassin.py", label="Voir la synthèse du bassin", icon="🗺️")
