import plotly.graph_objects as go
import streamlit as st

from app_state import basin_performance, chart, meta_table, page_setup, require_stations, usable_stations
from ews import theme as T
from ews.plots import heatmap

page_setup("Synthèse des stations", icon="🗺️")
obs, gl = require_stations()
all_st = usable_stations(obs, gl)
stations = st.multiselect("Stations", all_st, default=all_st)
if not stations:
    st.stop()
with st.spinner("Correction et calcul des performances…"):
    perf = basin_performance(obs, gl, tuple(stations))
cor = perf[perf["Series"] == "Corrected"]

# ------------------------------------------------------------------ map coloured by skill
m = meta_table()
m = m[m["station"].isin(stations)].dropna(subset=["lat", "lon"])
if len(m):
    lead = st.select_slider("Échéance affichée sur la carte", list(range(1, 8)), 1, format_func=lambda x: f"{x} jour(s)")
    k = cor[cor["Lead"] == lead].set_index("Station")["KGE"]
    m["KGE"] = m["station"].map(k)
    fig = go.Figure(go.Scattermap(lat=m["lat"], lon=m["lon"], mode="markers+text", text=m["station"],
                                  textposition="top right",
                                  marker=dict(size=18, color=m["KGE"].clip(-1, 1), colorscale=T.DIVERGING, cmin=-1,
                                              cmax=1, colorbar=dict(title=f"KGE {lead} j", thickness=10)),
                                  customdata=m[["river", "KGE"]].values,
                                  hovertemplate="<b>%{text}</b> (%{customdata[0]})<br>KGE = %{customdata[1]:.2f}<extra></extra>"))
    fig.update_layout(map=dict(style="open-street-map", center=dict(lat=m["lat"].mean(), lon=m["lon"].mean()), zoom=8.5),
                      height=420, margin=dict(l=0, r=0, t=0, b=0))
    chart(fig)

series = st.segmented_control("Série", ["Corrected", "Raw GloFAS", "Persistence"], default="Corrected",
                              format_func={"Corrected": "GloFAS corrigé", "Raw GloFAS": "GloFAS brut",
                                           "Persistence": "Persistance"}.get) or "Corrected"
p = perf[perf["Series"] == series]
tabs = st.tabs(["KGE", "NSE", "PBIAS", "RSR"])
for t, metric in zip(tabs, ["KGE", "NSE", "PBIAS", "RSR"]):
    with t:
        chart(heatmap(p, metric), key=f"hm_{metric}")

st.subheader("Classement (GloFAS corrigé)")
pers = perf[perf["Series"] == "Persistence"].set_index(["Station", "Lead"])["NSE"]
tab = cor.pivot(index="Station", columns="LeadTime", values="KGE")[["1D", "3D", "5D", "7D"]].add_prefix("KGE ")
tab["NSE 7D"] = cor[cor["Lead"] == 7].set_index("Station")["NSE"]
tab["Gain NSE 7D vs persistance"] = tab["NSE 7D"] - pers.xs(7, level="Lead")
st.dataframe(tab.sort_values("KGE 1D", ascending=False).round(2), width="stretch")
st.download_button("Télécharger toutes les performances (CSV)", perf.to_csv(index=False).encode(),
                   "performance_bassin.csv", "text/csv")
