import pandas as pd
import streamlit as st

from app_state import chart, corrected, current_station, glofas_dict, obs_wide, page_setup, registry
from ews.plots import annual_max, monthly_bars
from ews.statistics import annual_series, critical_days, detection_table, fit_distributions, mk_hamed_rao

page_setup("Tendances, crues de référence et jours critiques", icon="📊")
if not registry():
    st.warning("Aucune station chargée."); st.page_link("pages/1_Stations.py", label="Charger les stations"); st.stop()
obs = obs_wide()
name = current_station()
o_all = obs[name].dropna()

c1, c2, c3 = st.columns(3)
y0, y1 = int(o_all.index.year.min()), int(o_all.index.year.max())
years = c1.slider("Années", y0, y1, (max(y0, 2009) if y1 > 2009 else y0, y1))
q_crit = c2.slider("Seuil des jours critiques (quantile)", 0.75, 0.99, 0.90, 0.01)
drop = c3.toggle("Exclure les années incomplètes", value=False,
                 help="Années avec moins de 25 % des mesures habituelles. Désactivé = méthode de l'article.")
minf = 0.25 if drop else 0.0
am = annual_series(o_all, years[0], years[1], minf)
o = o_all.loc[str(years[0]):str(years[1])]
st.markdown(f"**Station : {name}** – {len(am)} années")
if len(am) < 5:
    st.warning("Moins de 5 années : analyse fréquentielle impossible."); st.stop()

# ------------------------------------------------------------------ trends
t1, t2 = st.columns(2)
for col, v, lab in ((t1, "AMAX", "Maximum annuel"), (t2, "MEAN", "Moyenne annuelle")):
    r = mk_hamed_rao(am[v].values)
    arrow = {"increasing": "↗ hausse", "decreasing": "↘ baisse"}.get(r["trend"], "→ pas de tendance")
    col.metric(f"Tendance – {lab} (Mann-Kendall modifié)", arrow,
               delta=f"Sen : {r['sen_slope']:+.2f} m³/s/an · p = {r['p']:.3f}", delta_color="off")

# ------------------------------------------------------------------ frequency
f = fit_distributions(am["AMAX"])
c1, c2 = st.columns(2)
with c1:
    chart(annual_max(am, {f"{T} ans": f["Gumbel"]["q"](T) for T in (2, 5, 10)}, f"{name} – maxima annuels et crues (Gumbel)"))
with c2:
    chart(monthly_bars(critical_days(o, q_crit), f"{name} – jours critiques (Q ≥ Q{int(q_crit*100)}) par mois"))

rp = pd.DataFrame({"Période de retour (ans)": [2, 5, 10, 25, 50, 100]})
for m_ in ("Gumbel", "GEV", "Normal"):
    rp[m_] = [f[m_]["q"](T) for T in rp["Période de retour (ans)"]]
aic = pd.DataFrame({"Loi": ["Gumbel", "GEV", "Normal"], "AIC": [f[m]["AIC"] for m in ("Gumbel", "GEV", "Normal")],
                    "BIC": [f[m]["BIC"] for m in ("Gumbel", "GEV", "Normal")]})
c1, c2 = st.columns([2, 1])
c1.markdown("**Débits de crue (m³/s)**"); c1.dataframe(rp.round(1), hide_index=True, width="stretch")
c2.markdown(f"**Ajustement** – meilleure loi : **{f['best']}**"); c2.dataframe(aic.round(1), hide_index=True, width="stretch")
c2.metric(f"Seuil d'alerte Q{int(q_crit*100)}", f"{o.quantile(q_crit):.1f} m³/s")

# ------------------------------------------------------------------ detection
gl = glofas_dict()
if name in gl:
    st.subheader("Détection des jours critiques par GloFAS")
    dt = detection_table(corrected(obs, gl, name), o_all.quantile(q_crit), name)
    st.dataframe(dt.drop(columns=["Station"]).round(1), hide_index=True, width="stretch")
    st.caption("Pour GloFAS brut, le seuil est le même quantile appliqué à la série GloFAS elle-même.")
st.download_button("Télécharger les crues de référence (CSV)", rp.to_csv(index=False).encode(),
                   f"{name}_crues.csv", "text/csv")
