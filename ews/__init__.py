"""GloFAS early-warning toolkit for the Rusizi basin (Burundi).

Implements the methodology of the paper "Performance Assessment and
Optimization of GloFAS Forecasts on the Rusizi River Basin for Enhanced
Anticipatory Flood Action":

* real-time updating (error persistence) of GloFAS forecasts
* continuous scores (KGE, NSE, PBIAS, RSR) and contingency scores
  (POD, FAR, LR, ROC, CSI)
* modified Mann-Kendall trend test (Hamed & Rao, 1998) and Sen's slope
* Gumbel / GEV / Normal frequency analysis, return periods, critical days
* operational 7-day corrected forecast from today's observation
"""
__version__ = "1.0.0"
LEADS = list(range(1, 8))
LT_COLS = [f"LT_{L}J" for L in LEADS]
