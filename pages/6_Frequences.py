import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app_state import corrected, require_data, sidebar_status, usable_stations
from ews.statistics import annual_series, critical_days, detection_table, fit_distributions, mk_hamed_rao

sidebar_status()
st.title("📊 6 · Tendances, analyse fréquentielle et jours critiques")
obs, gl = require_data()

c1, c2, c3 = st.columns(3)
y0, y1 = int(obs.index.year.min()), int(obs.index.year.max())
years = c1.slider("Années", y0, y1, (max(y0, 2009), y1))
q_crit = c2.slider("Seuil des jours critiques (quantile)", 0.75, 0.99, 0.90, 0.01)
drop = c3.checkbox("Exclure les années incomplètes (< 25 % des mesures habituelles)", value=False,
                   help="Désactivé = méthode de l'article (toutes les années ayant des données).")
minf = 0.25 if drop else 0.0
stations = [s for s in obs.columns if obs[s].dropna().size > 50]

# ---------------------------------------------------------------- trends
st.subheader("Tendances – test de Mann-Kendall modifié (Hamed & Rao, 1998) et pente de Sen")
tr = []
for s in stations:
    am = annual_series(obs[s], years[0], years[1], minf)
    for v in ("AMAX", "MEAN"):
        r = mk_hamed_rao(am[v].values)
        tr.append({"Station": s, "Série": "Maximum annuel" if v == "AMAX" else "Moyenne annuelle", **r})
st.dataframe(pd.DataFrame(tr).round(4), width="stretch", hide_index=True)

# ---------------------------------------------------------------- frequency
st.subheader("Analyse fréquentielle des maxima annuels")
rows, fits_all = [], {}
for s in stations:
    am = annual_series(obs[s], years[0], years[1], minf)
    if len(am) < 5:
        continue
    f = fit_distributions(am["AMAX"]); fits_all[s] = (am, f)
    o = obs[s].loc[str(years[0]):str(years[1])].dropna()
    r = {"Station": s, "Années": len(am), "Meilleure loi (AIC)": f["best"]}
    r.update({f"AIC {m}": f[m]["AIC"] for m in ("Gumbel", "GEV", "Normal")})
    r.update({f"Q{T} Gumbel": f["Gumbel"]["q"](T) for T in (2, 5, 10, 25, 50, 100)})
    r.update({f"Q{T} GEV": f["GEV"]["q"](T) for T in (2, 5, 10, 25)})
    r[f"Q{int(q_crit*100)} (seuil)"] = o.quantile(q_crit)
    rows.append(r)
freq = pd.DataFrame(rows)
st.dataframe(freq.round(1), width="stretch", hide_index=True)
st.download_button("Télécharger (CSV)", freq.to_csv(index=False).encode(), "analyse_frequentielle.csv", "text/csv")

s = st.selectbox("Station à afficher", list(fits_all))
am, f = fits_all[s]
o = obs[s].loc[str(years[0]):str(years[1])].dropna()
c1, c2 = st.columns(2)
fig = go.Figure(go.Scatter(x=am.index, y=am["AMAX"], mode="lines+markers", name="Maximum annuel observé",
                           line=dict(color="#222", width=2)))
for T, dash in ((2, "dot"), (5, "dash"), (10, "dashdot")):
    fig.add_hline(y=f["Gumbel"]["q"](T), line=dict(color="#2a78d6", dash=dash), annotation_text=f"{T} ans")
fig.update_layout(title=f"{s} – maxima annuels et crues Gumbel", height=360, yaxis_title="Débit (m³/s)",
                  margin=dict(l=10, r=10, t=50, b=10))
c1.plotly_chart(fig, width="stretch")
cd = critical_days(o, q_crit)
fig2 = go.Figure(go.Bar(x=list("JFMAMJJASOND"), y=cd["CriticalDays"], marker_color="#2a78d6"))
fig2.update_layout(title=f"{s} – jours critiques (Q ≥ Q{int(q_crit*100)}) par mois", height=360,
                   margin=dict(l=10, r=10, t=50, b=10))
c2.plotly_chart(fig2, width="stretch")

# ---------------------------------------------------------------- detection
st.subheader("Détection des jours critiques par GloFAS (corrigé vs brut)")
det = []
for s in usable_stations(obs, gl):
    d = corrected(obs, gl, s)
    det.append(detection_table(d, obs[s].dropna().quantile(q_crit), s))
if det:
    dt = pd.concat(det)
    st.dataframe(dt.round(1), width="stretch", hide_index=True)
    st.caption("Pour le GloFAS brut, le seuil est le même quantile appliqué à la série GloFAS elle-même.")
