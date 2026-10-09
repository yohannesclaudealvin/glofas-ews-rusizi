import pandas as pd
import streamlit as st

from app_state import chart, corrected, glofas_dict, num, obs_wide, page_setup, registry, thresholds
from ews.animation import animated_figure, animated_gif, frame_dates, relative_thresholds
from ews.geo import fetch_rivers, match_river

page_setup("Carte animée des débits", "Le comportement des cours d'eau dans le temps : la couleur de la rivière suit "
           "le niveau d'alerte et son épaisseur suit le débit.", icon="🎞️")

reg = registry()
located = [n for n, s in sorted(reg.items()) if num(s["lat"]) is not None and num(s["lon"]) is not None]
if not located:
    st.warning("Aucune station avec coordonnées. Ajoutez-en dans la page 1 · Stations.")
    st.page_link("pages/1_Stations.py", label="Charger les stations", icon="📂")
    st.stop()


@st.cache_data(ttl=7 * 24 * 3600, show_spinner=False)
def rivers(lat, lon):
    return fetch_rivers(lat, lon, radius_m=25000)


@st.cache_data(show_spinner=False, max_entries=8)
def make_gif(key, _stations, _dates, title, _others):
    return animated_gif(_stations, _dates, title=title, other_ways=_others)


SERIES = ["Débits observés", "GloFAS corrigé (échéance 1 j)", "GloFAS brut (échéance 1 j)", "Dernière prévision (page 8)"]
c1, c2, c3 = st.columns([2, 1.3, 1])
cur = st.session_state.get("station")
sel = c1.multiselect("Stations", located, default=[cur] if cur in located else located[:1],
                     help="Une station : sa rivière en détail. Plusieurs : vue du bassin.")
kind = c2.selectbox("Données", SERIES)
others = c3.toggle("Autres cours d'eau", value=False)
if not sel:
    st.stop()

obs = obs_wide()
gl = glofas_dict()
fc = st.session_state.get("one_res")
series, missing = {}, []
for n in sel:
    s = reg[n]
    if kind == "Débits observés":
        x = s["obs"]
    elif kind.startswith("GloFAS"):
        if s["glofas"] is None or n not in obs.columns:
            x = pd.Series(dtype=float)
        else:
            d = corrected(obs, gl, n)
            x = d["COR_1J" if "corrigé" in kind else "LT_1J"]
    else:
        if fc and fc["name"] == n:
            r = fc["res"]
            x = pd.concat([pd.Series([fc["q"]], index=[pd.Timestamp(fc["t0"])]),
                           pd.Series(r["corrected"].values, index=pd.to_datetime(r["valid_date"]))])
        else:
            x = pd.Series(dtype=float)
    x = x.dropna()
    if len(x):
        series[n] = x
    else:
        missing.append(n)
if missing:
    st.info("Pas de données « " + kind + " » pour : " + ", ".join(missing) +
            (". Lancez d'abord une prévision dans la page 8." if kind.startswith("Dernière") else "."))
if not series:
    st.stop()

lo = min(s.index.min() for s in series.values()).date()
hi = max(s.index.max() for s in series.values()).date()
if kind.startswith("Dernière"):
    start, end = lo, hi
else:
    default_start = max(lo, (pd.Timestamp(hi) - pd.DateOffset(years=1)).date())
    start, end = st.slider("Période", min_value=lo, max_value=hi, value=(default_start, hi), format="DD/MM/YYYY")

stations, all_ways = [], []
with st.spinner("Tracé des cours d'eau (OpenStreetMap)…"):
    for n, x in series.items():
        s = reg[n]
        try:
            ways = rivers(round(s["lat"], 3), round(s["lon"], 3))
        except Exception as e:
            ways = []
            st.warning(f"Tracé des rivières indisponible pour {n} : {e}")
        _, rw = match_river(ways, s["river"], n)
        all_ways += [w for w in ways if w not in rw]
        th0 = thresholds(obs, n) if n in obs.columns else {}
        th = ({"Jaune": th0["Vigilance"], "Orange": th0["Alerte"], "Rouge": th0["Alerte maximale"]} if th0
              else relative_thresholds(x))
        stations.append(dict(name=n, river=s["river"], lat=s["lat"], lon=s["lon"], ways=rw, series=x, th=th))

dates = frame_dates(list(series.values()), start, end, max_frames=120)
if len(dates) < 2:
    st.warning("Pas assez de dates dans la période choisie.")
    st.stop()
focus = st.selectbox("Hydrogramme affiché sous la carte", [s["name"] for s in stations]) if len(stations) > 1 \
    else stations[0]["name"]
fi = [s["name"] for s in stations].index(focus)
title = f"{kind}"
fig = animated_figure(stations, dates, focus=fi, title=title, other_ways=all_ways if others else None)
chart(fig, key="anim_map")
st.caption(f"{len(dates)} images. ▶ Lecture pour animer, ou faites glisser le curseur des dates. "
           "Couleurs : 🟢 sous le seuil jaune · 🟡 jaune · 🟠 orange · 🔴 rouge. "
           + ("Seuils de la station (Q90, crues de 2 et 5 ans)" if any(n in obs.columns for n in series)
              else "Seuils relatifs (percentiles 75, 90 et 97 de la série)") + ".")

a, b, c = st.columns(3)
tag = "_".join(series)[:40]
a.download_button("⬇️ Animation interactive (HTML)", fig.to_html(include_plotlyjs="cdn", auto_play=False).encode(),
                  f"animation_{tag}.html", "text/html", width="stretch")
if b.button("🎞️ Préparer le GIF animé", width="stretch"):
    with st.spinner("Fabrication du GIF (quelques secondes)…"):
        key = (tuple(series), kind, str(start), str(end), others, focus)
        st.session_state["gif"] = (key, make_gif(key, [stations[fi]] + [s for i, s in enumerate(stations) if i != fi],
                                                 dates, title, all_ways if others else None))
g = st.session_state.get("gif")
if g:
    b.download_button("⬇️ Télécharger le GIF", g[1], f"animation_{tag}.gif", "image/gif", width="stretch")
c.download_button("⬇️ Données (CSV)", pd.concat(series, axis=1).loc[str(start):str(end)].to_csv().encode(),
                  f"debits_{tag}.csv", "text/csv", width="stretch")
if g:
    with st.expander("Aperçu du GIF"):
        st.image(g[1])
