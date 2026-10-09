import streamlit as st

from app_state import corrected, require_data, sidebar_status, usable_stations
from ews import LEADS
from ews.metrics import kge, nse
from ews.plots import hydrograph

sidebar_status()
st.title("〰️ 5 · Similarité observations / prévisions")
obs, gl = require_data()
c1, c2 = st.columns([2, 1])
s = c1.selectbox("Station", usable_stations(obs, gl))
mode = c2.radio("Affichage", ["Une échéance", "Les 7 échéances"], horizontal=True)
d = corrected(obs, gl, s)
rng = st.slider("Période", d.index.min().to_pydatetime(), d.index.max().to_pydatetime(),
                (d.index.min().to_pydatetime(), d.index.max().to_pydatetime()), format="YYYY-MM")
dd = d.loc[rng[0]:rng[1]]
leads = [st.select_slider("Échéance (jours)", LEADS, 1)] if mode == "Une échéance" else LEADS
for L in leads:
    t = f"{s} – {L} jour(s) · KGE corrigé {kge(dd[f'COR_{L}J'], dd['OBS']):.2f}, NSE {nse(dd[f'COR_{L}J'], dd['OBS']):.2f}"
    st.plotly_chart(hydrograph(dd, L, t), width="stretch")
