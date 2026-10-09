"""Regression tests: the Python core must reproduce the paper / R results."""
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from ews.correction import ForecastArchive, correct_station, operational_forecast, performance_table
from ews.data_io import load_sample, merge_station
from ews.statistics import annual_series, frequency_table, mk_hamed_rao

SAMPLE = Path(__file__).parents[1] / "data" / "sample"
pytestmark = pytest.mark.skipif(not SAMPLE.exists(), reason="sample data not present")

# values of Figure 3 / Table 2 of the paper (v2) - corrected forecasts
EXPECTED = {
    "RUSIZI": {"KGE1": 0.92, "NSE1": 0.88, "KGE7": 0.60, "NSE7": 0.25, "Q2": 221.3, "Q10": 293.8},
    "KABURANTWA": {"KGE1": 0.98, "NSE1": 0.97, "KGE7": 0.92, "NSE7": 0.85, "Q2": 32.8, "Q10": 52.7},
    "MPANDA": {"KGE1": 0.66, "NSE1": 0.28, "KGE7": 0.30, "NSE7": -0.76, "Q2": 23.2, "Q10": 44.2},
}


@pytest.fixture(scope="module")
def data():
    return load_sample(SAMPLE)


@pytest.mark.parametrize("st", list(EXPECTED))
def test_performance(data, st):
    obs, gl = data
    p = performance_table(correct_station(merge_station(obs, gl[st], st)), st)
    c = p[p.Series == "Corrected"].set_index("Lead")
    e = EXPECTED[st]
    assert round(c.loc[1, "KGE"], 2) == e["KGE1"] and round(c.loc[1, "NSE"], 2) == e["NSE1"]
    assert round(c.loc[7, "KGE"], 2) == e["KGE7"] and round(c.loc[7, "NSE"], 2) == e["NSE7"]


@pytest.mark.parametrize("st", list(EXPECTED))
def test_frequency(data, st):
    obs, _ = data
    t, _ = frequency_table(obs[st].loc["2009":"2023"], st)
    assert round(t["Q2 Gumbel"][0], 1) == EXPECTED[st]["Q2"]
    assert round(t["Q10 Gumbel"][0], 1) == EXPECTED[st]["Q10"]


def test_trend_rusizi(data):
    obs, _ = data
    r = mk_hamed_rao(annual_series(obs["RUSIZI"], 2009, 2023)["AMAX"])
    assert r["trend"] == "increasing" and abs(r["sen_slope"] - 9.85) < 0.01


def test_operational_forecast():
    idx = pd.date_range("2026-10-09", periods=8, freq="D")
    fc = pd.DataFrame({"river_discharge": np.arange(100, 108, dtype=float)}, index=idx)
    res = operational_forecast(fc, idx[0], q_obs_today=40.0)
    assert list(res["corrected"]) == [41, 42, 43, 44, 45, 46, 47]          # error -60 added
    # with an archived 2-day forecast valid today = 90 -> lead-2 error = 40 - 90 = -50
    arch = ForecastArchive(pd.DataFrame({"station": ["X"], "issue_date": ["2026-10-07"], "valid_date": ["2026-10-09"],
                                         "lead": [2], "q": [90.0]}))
    res2 = operational_forecast(fc, idx[0], 40.0, arch.df, station="X")
    assert res2.loc[res2.lead == 2, "corrected"].iloc[0] == 102 - 50
    assert res2.loc[res2.lead == 1, "corrected"].iloc[0] == 101 - 60
