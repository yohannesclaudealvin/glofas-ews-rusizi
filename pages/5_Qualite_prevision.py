import pandas as pd
import streamlit as st

from app_state import chart, corrected, frequency, page_setup, require_stations, usable_stations
from ews import LEADS
from ews.metrics import contingency
from ews.plots import heatmap

page_setup("Qualité des prévisions d'événements", icon="🎯")
obs, gl = require_stations()

c1, c2 = st.columns([2, 1])
stations = c1.multiselect("Stations", usable_stations(obs, gl), default=usable_stations(obs, gl))
kind = c2.selectbox("Seuil d'événement", ["Débit moyen observé (article)", "Quantile observé",
                                          "Crue de période de retour (Gumbel)", "Valeur fixe (m³/s)"])
q = T = val = None
if kind == "Quantile observé":
    q = st.slider("Quantile", 0.50, 0.99, 0.90, 0.01)
elif kind.startswith("Crue"):
    T = st.segmented_control("Période de retour (ans)", [2, 5, 10, 25], default=2) or 2
elif kind.startswith("Valeur"):
    val = st.number_input("Seuil (m³/s)", min_value=0.0, value=50.0)

rows = []
for s in stations:
    d = corrected(obs, gl, s)
    thr = (d["OBS"].mean() if kind.startswith("Débit moyen") else d["OBS"].quantile(q) if q is not None
           else float(frequency(obs, s)[f"Q{T} Gumbel"].iloc[0]) if T is not None else val)
    for L in LEADS:
        rows.append({"Station": s, "LeadTime": f"{L}D", "Seuil (m³/s)": thr,
                     **contingency(d["OBS"] >= thr, d[f"COR_{L}J"] >= thr)})
if not rows:
    st.stop()
sk = pd.DataFrame(rows)
tabs = st.tabs(["POD", "FAR", "LR", "ROC", "CSI"])
for t, m in zip(tabs, ["POD", "FAR", "LR", "ROC", "CSI"]):
    with t:
        chart(heatmap(sk, m), key=f"q_{m}")
with st.expander("Tableau complet (a = succès, b = fausses alarmes, c = manqués, d = rejets corrects)"):
    st.dataframe(sk.round(2), width="stretch", hide_index=True)
st.download_button("Télécharger (CSV)", sk.to_csv(index=False).encode(), "qualite_prevision.csv", "text/csv")
