import pandas as pd
import streamlit as st

from app_state import corrected, frequency, require_data, sidebar_status, usable_stations
from ews import LEADS
from ews.metrics import contingency
from ews.plots import heatmap

sidebar_status()
st.title("🎯 4 · Qualité des prévisions d'événements")
obs, gl = require_data()
st.markdown("Un **événement** est un débit supérieur ou égal au seuil choisi. **FAR** est ici le *taux* de fausses "
            "alarmes b/(b+d), comme dans la Figure 4 de l'article. **LR** = POD/FAR (le « RV » du texte) et "
            "**ROC** = POD − FAR. Le **CSI** et le *ratio* de fausses alarmes b/(a+b) sont aussi donnés.")

stations = st.multiselect("Stations", usable_stations(obs, gl), default=usable_stations(obs, gl))
thr_kind = st.selectbox("Seuil d'événement", ["Débit moyen observé (Figure 4 de l'article)", "Quantile observé",
                                              "Crue de période de retour (Gumbel)", "Valeur fixe (m³/s)"])
q = T = val = None
if thr_kind == "Quantile observé":
    q = st.slider("Quantile", 0.50, 0.99, 0.90, 0.01)
elif thr_kind.startswith("Crue"):
    T = st.selectbox("Période de retour (ans)", [2, 5, 10, 25])
elif thr_kind.startswith("Valeur"):
    val = st.number_input("Seuil (m³/s)", min_value=0.0, value=50.0)

rows = []
for s in stations:
    d = corrected(obs, gl, s)
    if thr_kind.startswith("Débit moyen"):
        thr = d["OBS"].mean()
    elif q is not None:
        thr = d["OBS"].quantile(q)
    elif T is not None:
        thr = float(frequency(obs, s)[f"Q{T} Gumbel"].iloc[0])
    else:
        thr = val
    for L in LEADS:
        c = contingency(d["OBS"] >= thr, d[f"COR_{L}J"] >= thr)
        rows.append({"Station": s, "LeadTime": f"{L}D", "Threshold": thr, **c})
if not rows:
    st.stop()
sk = pd.DataFrame(rows)
h = 80 + 38 * len(stations)
c1, c2 = st.columns(2)
c1.plotly_chart(heatmap(sk, "POD", height=h), width="stretch")
c2.plotly_chart(heatmap(sk, "FAR", height=h), width="stretch")
c1.plotly_chart(heatmap(sk, "LR", height=h), width="stretch")
c2.plotly_chart(heatmap(sk, "ROC", height=h), width="stretch")
c1.plotly_chart(heatmap(sk, "CSI", height=h), width="stretch")
c2.plotly_chart(heatmap(sk, "FAR_ratio", height=h), width="stretch")
st.caption("Critère d'acceptabilité utilisé dans l'article : LR ≥ 6 (taux de succès au moins six fois supérieur au "
           "taux de fausses alarmes).")
st.dataframe(sk.round(2), width="stretch", hide_index=True)
st.download_button("Télécharger (CSV)", sk.to_csv(index=False).encode(), "qualite_prevision.csv", "text/csv")
