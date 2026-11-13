"""JSON-safety helpers: pandas/numpy objects don't serialize cleanly through
FastAPI's default encoder (NaN isn't valid JSON, np.float64 trips some
encoders), so every analytics output passes through here before leaving the
API boundary.
"""

import math

import numpy as np
import pandas as pd


def safe_float(x) -> float | None:
    if x is None:
        return None
    try:
        xf = float(x)
    except (TypeError, ValueError):
        return None
    if math.isnan(xf) or math.isinf(xf):
        return None
    return round(xf, 6)


def series_to_points(series: pd.Series | None) -> list[dict]:
    if series is None or series.empty:
        return []
    out = []
    for idx, value in series.items():
        v = safe_float(value)
        out.append({"date": _fmt_date(idx), "value": v})
    return out


def _fmt_date(idx) -> str:
    if hasattr(idx, "date"):
        return idx.date().isoformat() if hasattr(idx, "hour") else idx.isoformat()
    return str(idx)


def latest_value(series: pd.Series | None) -> float | None:
    if series is None or series.empty:
        return None
    return safe_float(series.iloc[-1])
