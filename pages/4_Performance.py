import streamlit as st

from app_state import chart, corrected, current_station, page_setup, performance, require_stations
from ews.plots import heatmap, lead_lines

page_setup("Correction et performance", icon="📈")
obs, gl = require_stations()
name = current_station(require_glofas=True)
st.markdown(f"**Station : {name}** (changez de station dans la barre latérale)")
st.latex(r"Q_{corr,L}(t) = Q_{GloFAS,L}(t) + \left[\,Q_{obs}(t-L) - Q_{GloFAS,L}(t-L)\,\right]")

perf = performance(obs, gl, name)
d = corrected(obs, gl, name)
c = st.columns(4)
c[0].metric("Dates communes", f"{len(d)}")
c[1].metric("Débit moyen observé", f"{d['OBS'].mean():.2f} m³/s")
c[2].metric("GloFAS brut moyen (1 j)", f"{d['LT_1J'].mean():.2f} m³/s",
            delta=f"{100 * (d['LT_1J'].mean() / d['OBS'].mean() - 1):+.0f} % biais", delta_color="off")
k1 = perf[(perf.Series == "Corrected") & (perf.Lead == 1)]["KGE"].iloc[0]
c[3].metric("KGE corrigé (1 j)", f"{k1:.2f}")

p2 = perf.assign(Row=perf["Series"].map({"Corrected": "Corrigé", "Raw GloFAS": "Brut", "Persistence": "Persistance"}))
tabs = st.tabs(["KGE", "NSE", "PBIAS", "RSR"])
for t, m in zip(tabs, ["KGE", "NSE", "PBIAS", "RSR"]):
    with t:
        c1, c2 = st.columns([3, 2])
        with c1:
            chart(heatmap(p2, m, row="Row", height=260), key=f"h_{m}")
        with c2:
            if m in ("KGE", "NSE", "RSR"):
                chart(lead_lines(perf, m), key=f"l_{m}")
with st.expander("Tableau complet"):
    st.dataframe(perf.round(3), width="stretch", hide_index=True)
c1, c2 = st.columns(2)
c1.download_button("Série corrigée (CSV)", d.to_csv().encode(), f"{name}_corrige.csv", "text/csv")
c2.download_button("Tableau de performance (CSV)", perf.to_csv(index=False).encode(), f"{name}_performance.csv", "text/csv")
