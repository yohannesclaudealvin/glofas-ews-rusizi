"""Copernicus files (NetCDF/zip, control + perturbed), snapping on the GloFAS network, ensemble
exceedance probabilities and station list import (python -m pytest tests/test_glofas_files.py)."""
import io
import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

sys.path.insert(0, str(Path(__file__).parents[1]))
from ews.correction import exceedance, operational_forecast  # noqa: E402
from ews.data_io import read_points  # noqa: E402
from ews.glofas_netcdf import extract_point  # noqa: E402
from ews.snap import snap_on_grid  # noqa: E402

T0 = pd.Timestamp("2026-10-09")
LATS = np.arange(-3.025, -3.6, -0.05)
LONS = np.arange(29.175, 29.6, 0.05)


def _ds(nmem, first):
    rng = np.random.default_rng(first)
    base = np.full((len(LATS), len(LONS)), 2.0)
    base[5, 3] = 150.0                                    # the river cell
    d = base[None, None] * (1 + 0.01 * np.arange(30)[None, :, None, None]) + \
        rng.normal(0, 0.5, (nmem, 30, len(LATS), len(LONS)))
    x = xr.Dataset({"dis24": (("number", "step", "latitude", "longitude"), d.astype("float32"))},
                   coords={"number": np.arange(first, first + nmem), "step": pd.to_timedelta(np.arange(1, 31), "D"),
                           "latitude": LATS, "longitude": LONS, "time": T0})
    return x.assign_coords(valid_time=("step", (T0 + x["step"].to_index()).values))


def _nc(x):
    b = io.BytesIO()
    x.to_netcdf(b, engine="h5netcdf")
    return b.getvalue()


def _bundle():
    z = io.BytesIO()
    with zipfile.ZipFile(z, "w") as f:
        f.writestr("control.nc", _nc(_ds(1, 0).isel(number=0)))
    return {"control": z.getvalue(), "perturbed": _nc(_ds(50, 1))}


STATION = (LATS[5] + 0.04, LONS[3] - 0.045)              # ~6 km from the river cell


def test_extract_nearest_and_members():
    fc = extract_point(_bundle(), *STATION)
    assert fc.attrs["status"] == "ok" and fc.index.min() == T0 and len(fc) == 30
    assert sum(c.startswith("river_discharge_member") for c in fc.columns) == 50
    assert fc["river_discharge"].iloc[0] < 10             # nearest cell is not on the river


def test_snapping_moves_to_river_cell():
    fc = extract_point(_bundle(), *STATION, radius_km=10)
    assert fc.attrs["status"] == "recalé"
    assert abs(fc.attrs["cell"][0] - LATS[5]) < 1e-6 and abs(fc.attrs["cell"][1] - LONS[3]) < 1e-6
    assert fc["river_discharge"].iloc[0] > 140


def test_snap_fallback():
    stat = np.zeros((len(LATS), len(LONS)))
    assert snap_on_grid(LATS, LONS, stat, *STATION, radius_km=5)["status"] == "repli"


def test_exceedance_probabilities():
    fc = extract_point(_bundle(), *STATION, radius_km=10)
    res = operational_forecast(fc, T0, 120.0, leads=range(1, 8))
    out = exceedance(fc, res, {"Jaune": 100.0, "Orange": 125.0, "Rouge": 1000.0})
    assert (out["n_membres"] == 51).all()
    assert (out["p_Jaune"] == 100).all() and (out["p_Rouge"] == 0).all()
    raw = exceedance(fc, res, {"Jaune": 100.0}, raw=True)
    assert (raw["p_Jaune"] == 100).all()


def test_read_points_aliases():
    pts = read_points(b"Code station;Longitude (deg);Latitude;Riviere\nmugere;29.35;-3.48;Mugere\n")
    assert list(pts.columns) == ["station", "river", "lat", "lon"]
    assert pts.iloc[0]["station"] == "MUGERE" and pts.iloc[0]["lon"] == 29.35
