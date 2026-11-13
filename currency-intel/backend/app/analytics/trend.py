"""Trend and momentum classification built on top of the moving averages
and ROC/momentum series from indicators.py.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class TrendResult:
    direction: str  # "uptrend" | "downtrend" | "sideways"
    momentum_state: str  # "accelerating_up" | "decelerating_up" | "accelerating_down" | "decelerating_down" | "flat"
    reversal_signal: str | None  # "bullish_crossover" | "bearish_crossover" | None
    short_vs_long_pct: float | None


def classify_trend(short_ma: pd.Series, long_ma: pd.Series, flat_threshold_pct: float = 0.3) -> tuple[str, float | None]:
    s, l = short_ma.iloc[-1], long_ma.iloc[-1]
    if np.isnan(s) or np.isnan(l) or l == 0:
        return "unknown", None
    diff_pct = float((s - l) / abs(l) * 100.0)
    if diff_pct > flat_threshold_pct:
        return "uptrend", diff_pct
    if diff_pct < -flat_threshold_pct:
        return "downtrend", diff_pct
    return "sideways", diff_pct


def classify_momentum(roc_series: pd.Series, lookback: int = 5) -> str:
    clean = roc_series.dropna()
    if len(clean) < lookback + 1:
        return "unknown"
    recent, prior = clean.iloc[-1], clean.iloc[-1 - lookback]
    if recent > 0 and recent >= prior:
        return "accelerating_up"
    if recent > 0 and recent < prior:
        return "decelerating_up"
    if recent < 0 and recent <= prior:
        return "accelerating_down"
    if recent < 0 and recent > prior:
        return "decelerating_down"
    return "flat"


def detect_crossover(short_ma: pd.Series, long_ma: pd.Series, lookback: int = 5) -> str | None:
    diff = (short_ma - long_ma).dropna()
    if len(diff) < lookback + 1:
        return None
    window = diff.iloc[-lookback - 1 :]
    sign_changes = np.sign(window).diff().dropna()
    if (sign_changes > 0).any():
        return "bullish_crossover"
    if (sign_changes < 0).any():
        return "bearish_crossover"
    return None


def analyze(short_ma: pd.Series, long_ma: pd.Series, roc_series: pd.Series) -> TrendResult:
    direction, diff_pct = classify_trend(short_ma, long_ma)
    momentum_state = classify_momentum(roc_series)
    reversal = detect_crossover(short_ma, long_ma)
    return TrendResult(
        direction=direction,
        momentum_state=momentum_state,
        reversal_signal=reversal,
        short_vs_long_pct=diff_pct,
    )
