"""Runs every page of the app headlessly with the sample stations (python tests/apptest_all_pages.py)."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))
from ews.data_io import load_glofas, load_station_observations  # noqa: E402

SD = ROOT / "data" / "sample" / "stations"
META = pd.read_csv(ROOT / "config" / "stations.csv").set_index("station")
f = lambda v: float(v) if pd.notna(v) else None
reg = {}
for o in sorted(SD.glob("*_observations.csv")):
    n = o.name.split("_")[0]
    g = SD / f"{n}_glofas.xlsx"
    r = META.loc[n]
    reg[n] = {"river": r["river"], "lat": f(r["lat"]), "lon": f(r["lon"]), "cell_lat": f(r["cell_lat"]),
              "cell_lon": f(r["cell_lon"]), "obs": load_station_observations(o, o.name)[0],
              "glofas": load_glofas(g, g.name)[1] if g.exists() else None}

PAGES = ["pages/0_Accueil.py", "pages/1_Stations.py", "pages/2_Fiche_station.py", "pages/3_Bassin.py",
         "pages/4_Performance.py", "pages/5_Qualite_prevision.py", "pages/6_Similarite.py", "pages/7_Frequences.py",
         "pages/8_Prevision.py", "pages/9_Guide.py"]


def new_app(station="RUSIZI"):
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=240)
    at.session_state["stations"] = {k: dict(v) for k, v in reg.items()}
    at.session_state["station"] = station
    return at


ok = True
for p in PAGES:
    for stn in ("RUSIZI", "MPANDA"):
        at = new_app(stn); at.run(); at.switch_page(p); at.run()
        exc = [e.value for e in at.exception]
        ok &= not exc
        print(f"{p:32s} {stn:10s} exceptions={exc[:1]} errors={[e.value for e in at.error][:1]}")

# operational forecast with an imported forecast (no internet needed)
at = new_app()
today = pd.Timestamp("2026-10-09")
idx = pd.date_range(today - pd.Timedelta(days=7), periods=15, freq="D")
mk = lambda b: pd.DataFrame({c: b + off + np.linspace(0, 20, 15) for c, off in
                             [("river_discharge", 0), ("river_discharge_min", -5), ("river_discharge_p25", -2),
                              ("river_discharge_median", 0), ("river_discharge_p75", 3), ("river_discharge_max", 8)]},
                            index=idx)
at.session_state["manual_fc"] = {"RUSIZI": mk(500.0), "KABURANTWA": mk(15.0), "MPANDA": mk(50.0)}
at.session_state["q_RUSIZI"] = 255.0; at.session_state["q_KABURANTWA"] = 30.0; at.session_state["q_MPANDA"] = 9.0
at.run(); at.switch_page("pages/8_Prevision.py"); at.run()
at.date_input(key="batch_day").set_value(today.date()).run()
next(b for b in at.button if b.label.startswith("Télécharger GloFAS")).click().run()
print("forecast exceptions:", [e.value for e in at.exception])
for df in at.dataframe:
    if "Niveau max (7 j)" in df.value.columns:
        print(df.value.to_string())
ok &= not at.exception

# single-station forecast from a GloFAS NetCDF file (synthetic, same layout as the Copernicus file)
import io  # noqa: E402
import xarray as xr  # noqa: E402
t0 = pd.Timestamp("2026-10-09")
lats, lons = np.arange(-2.275, -4.5, -0.05), np.arange(28.975, 30.9, 0.05)
rng = np.random.default_rng(1)
dis = 400 + 15 * np.arange(30)[None, :, None, None] + rng.normal(0, 20, (51, 30, 1, 1)) + 0 * lats[None, None, :, None] \
      + 0 * lons[None, None, None, :]
ds = xr.Dataset({"dis24": (("number", "step", "latitude", "longitude"), dis.astype("float32"))},
                coords={"number": np.arange(51), "step": pd.to_timedelta(np.arange(1, 31), "D"),
                        "latitude": lats, "longitude": lons, "forecast_reference_time": t0})
ds = ds.assign_coords(valid_time=("step", (t0 + ds["step"].to_index()).values))
buf = io.BytesIO(); ds.to_netcdf(buf, engine="h5netcdf")
at = new_app()
at.session_state["nc"] = (buf.getvalue(), "test.nc")
at.run(); at.switch_page("pages/8_Prevision.py"); at.run()
at.radio(key="one_source").set_value("Fichier NetCDF").run()
at.number_input(key="obs_RUSIZI").set_value(255.0).run()
at.button(key="one_run").click().run()
res = at.session_state["one_res"]["res"] if "one_res" in at.session_state else None
print("one-station exceptions:", [e.value for e in at.exception])
print(res[["lead", "valid_date", "glofas_raw", "corrected", "niveau"]].to_string() if res is not None else "NO RESULT")
print("\n".join(at.session_state["fc_log"][-3:]))
ok &= not at.exception and res is not None and len(res) == 7
print("ALL OK" if ok else "FAILURES")
