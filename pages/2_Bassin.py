import streamlit as st

from app_state import basin_performance, require_data, sidebar_status, usable_stations
from ews.plots import heatmap

sidebar_status()
st.title("🗺️ 2 · Synthèse du bassin")
obs, gl = require_data()
stations = st.multiselect("Stations", usable_stations(obs, gl), default=usable_stations(obs, gl))
if not stations:
    st.stop()
with st.spinner("Correction et calcul des performances pour toutes les stations…"):
    perf = basin_performance(obs, gl, tuple(stations))

series = st.radio("Série", ["Corrected", "Raw GloFAS", "Persistence"], horizontal=True,
                  format_func={"Corrected": "GloFAS corrigé", "Raw GloFAS": "GloFAS brut",
                               "Persistence": "Persistance (dernière observation)"}.get)
p = perf[perf["Series"] == series]
h = 80 + 38 * len(stations)
c1, c2 = st.columns(2)
c1.plotly_chart(heatmap(p, "KGE", height=h), width="stretch")
c2.plotly_chart(heatmap(p, "NSE", height=h), width="stretch")
c1.plotly_chart(heatmap(p, "PBIAS", digits=1, height=h), width="stretch")
c2.plotly_chart(heatmap(p, "RSR", height=h, reverse=True), width="stretch")

st.subheader("Classement des stations (GloFAS corrigé)")
cor = perf[perf["Series"] == "Corrected"]
pers = perf[perf["Series"] == "Persistence"].set_index(["Station", "Lead"])["NSE"]
tab = cor.pivot(index="Station", columns="LeadTime", values="KGE")[[f"{L}D" for L in (1, 3, 5, 7)]].add_prefix("KGE ")
tab["NSE 1D"] = cor[cor["Lead"] == 1].set_index("Station")["NSE"]
tab["NSE 7D"] = cor[cor["Lead"] == 7].set_index("Station")["NSE"]
tab["Gain vs persistance, NSE 7D"] = tab["NSE 7D"] - pers.xs(7, level="Lead")
st.dataframe(tab.sort_values("KGE 1D", ascending=False).round(2), width="stretch")
st.caption("Persistance = on prévoit la dernière observation disponible (L pas de temps plus tôt). Un gain positif "
           "signifie que GloFAS corrigé apporte de l'information au-delà de la dernière observation.")
st.download_button("Télécharger toutes les performances (CSV)", perf.to_csv(index=False).encode(),
                   "performance_bassin.csv", "text/csv")
