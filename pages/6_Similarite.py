import streamlit as st

from app_state import chart, corrected, current_station, page_setup, require_stations
from ews import LEADS
from ews.metrics import kge, nse
from ews.plots import hydrograph

page_setup("Hydrogrammes observés et prévus", icon="〰️")
obs, gl = require_stations()
name = current_station(require_glofas=True)
d = corrected(obs, gl, name)

c1, c2 = st.columns([3, 1])
lead = c1.segmented_control("Échéance", LEADS, default=1, format_func=lambda x: f"{x} j") or 1
show_raw = c2.toggle("Afficher GloFAS brut", value=False)

k, n = kge(d[f"COR_{lead}J"], d["OBS"]), nse(d[f"COR_{lead}J"], d["OBS"])
chart(hydrograph(d, lead, f"{name} – échéance {lead} jour(s) · KGE {k:.2f} · NSE {n:.2f}", show_raw))
st.caption("Utilisez le curseur sous le graphique ou les boutons 1 an / 3 ans pour zoomer. Cliquez sur une "
           "légende pour masquer ou afficher une série. Icône 📷 : télécharger l'image en haute résolution.")
