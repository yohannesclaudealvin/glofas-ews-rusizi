"""Edge cases (python tests/apptest_edge_cases.py):
stations with empty (NaN) coordinates, and a forecast-only station without observations."""
import sys
from pathlib import Path

import pandas as pd
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))
from ews.data_io import load_glofas, load_station_observations  # noqa: E402

SD = ROOT / "data" / "sample" / "stations"
reg = {}
for n in ("RUSIZI", "MPANDA", "NTAHANGWA", "MUHIRA"):
    reg[n] = {"river": n.title(), "lat": -3.325, "lon": 29.225, "cell_lat": -3.325, "cell_lon": 29.225,
              "obs": load_station_observations(SD / f"{n}_observations.csv")[0],
              "glofas": load_glofas(SD / f"{n}_glofas.xlsx", f"{n}_glofas.xlsx")[1]}
for n in ("NTAHANGWA", "MUHIRA"):                       # coordinates left empty in the table -> NaN
    reg[n].update(lat=float("nan"), lon=float("nan"), cell_lat=float("nan"), cell_lon=float("nan"))
reg["GITEGA"] = {"river": "Ruvubu", "lat": -3.43, "lon": 29.92, "cell_lat": None, "cell_lon": None,
                 "obs": pd.Series(dtype=float, index=pd.DatetimeIndex([])), "glofas": None}

ok = True
for stn in ("RUSIZI", "NTAHANGWA", "GITEGA"):
    for page in ("pages/0_Accueil.py", "pages/1_Stations.py", "pages/2_Fiche_station.py", "pages/3_Bassin.py",
                 "pages/7_Frequences.py", "pages/8_Prevision.py"):
        at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=240)
        at.session_state["stations"] = {k: dict(v) for k, v in reg.items()}
        at.session_state["station"] = stn
        at.run(); at.switch_page(page); at.run()
        exc = [e.value[:150] for e in at.exception]
        ok &= not exc
        extra = ""
        if page.endswith("8_Prevision.py"):
            extra = "inputs=" + ",".join(n.label.split(" (")[0] for n in at.number_input)
        print(f"{stn:10s} {page:28s} exceptions={exc} {extra}")
print("ALL OK" if ok else "FAILURES")
