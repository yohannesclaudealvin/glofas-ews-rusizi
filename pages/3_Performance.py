import streamlit as st

from app_state import corrected, performance, require_data, sidebar_status, usable_stations
from ews.plots import heatmap, lead_lines

sidebar_status()
st.title("📈 3 · Correction en temps réel et performance")
obs, gl = require_data()
st.latex(r"Q_{corr,L}(t) = Q_{GloFAS,L}(t) + \left[\,Q_{obs}(t-L) - Q_{GloFAS,L}(t-L)\,\right]")
st.caption("Pas de temps = dates du fichier d'observations. La première valeur de chaque échéance n'a pas d'erreur "
           "antérieure et n'est pas corrigée.")

st_ = st.selectbox("Station", usable_stations(obs, gl))
perf = performance(obs, gl, st_)
d = corrected(obs, gl, st_)

c1, c2, c3 = st.columns(3)
c1.metric("Dates communes", len(d))
c2.metric("Débit moyen observé", f"{d['OBS'].mean():.2f} m³/s")
c3.metric("Débit moyen GloFAS brut (1 j)", f"{d['LT_1J'].mean():.2f} m³/s")

perf2 = perf.copy(); perf2["Row"] = perf2["Series"].map({"Corrected": "Corrigé", "Raw GloFAS": "Brut", "Persistence": "Persistance"})
cols = st.columns(2)
for i, (m, dig, rev) in enumerate((("KGE", 2, False), ("NSE", 2, False), ("PBIAS", 1, False), ("RSR", 2, True))):
    cols[i % 2].plotly_chart(heatmap(perf2, m, row="Row", digits=dig, height=230, reverse=rev), width="stretch")

st.subheader("Évolution avec l'échéance")
cols = st.columns(2)
for i, m in enumerate(("KGE", "NSE")):
    cols[i].plotly_chart(lead_lines(perf, m), width="stretch")

st.dataframe(perf.round(3), width="stretch", hide_index=True)
st.download_button("Télécharger la série corrigée (CSV)", d.to_csv().encode(), f"{st_}_corrige.csv", "text/csv")
st.download_button("Télécharger le tableau de performance (CSV)", perf.to_csv(index=False).encode(),
                   f"{st_}_performance.csv", "text/csv")
