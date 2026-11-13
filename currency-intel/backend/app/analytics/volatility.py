"""Volatility and downside-risk analytics.

Purpose, per the product brief: distinguish a currency becoming *cheaper*
from a currency becoming *riskier*. A currency can fall in price while
volatility stays low (orderly depreciation) or fall while volatility spikes
(disorderly / risky). Both the scoring engine and the UI need both numbers.
"""

import numpy as np
import pandas as pd

TRADING_DAYS_PER_YEAR = 252


def log_returns(series: pd.Series) -> pd.Series:
    return np.log(series / series.shift(1))


def rolling_std(returns: pd.Series, window: int) -> pd.Series:
    return returns.rolling(window=window, min_periods=max(2, window // 2)).std()


def annualized_volatility(returns: pd.Series, window: int) -> pd.Series:
    return rolling_std(returns, window) * np.sqrt(TRADING_DAYS_PER_YEAR)


def ewma_volatility(returns: pd.Series, lam: float = 0.94) -> pd.Series:
    """RiskMetrics-style EWMA variance, annualized.

    Reacts faster to recent shocks than a flat rolling window — a cheap,
    well-understood stand-in for a full GARCH(1,1) fit (see README for why
    we didn't implement GARCH/ARIMA in full).
    """
    sq = returns.fillna(0.0) ** 2
    var = sq.ewm(alpha=1 - lam, adjust=False, min_periods=5).mean()
    return np.sqrt(var) * np.sqrt(TRADING_DAYS_PER_YEAR)


def volatility_percentile(vol_series: pd.Series) -> float | None:
    """Where does the *latest* volatility reading sit versus its own history (0-100)?"""
    clean = vol_series.dropna()
    if len(clean) < 10:
        return None
    latest = clean.iloc[-1]
    return float((clean <= latest).mean() * 100.0)


def volatility_regime(percentile: float | None) -> str:
    if percentile is None:
        return "unknown"
    if percentile >= 85:
        return "high"
    if percentile >= 60:
        return "elevated"
    if percentile >= 30:
        return "normal"
    return "low"


def max_drawdown(series: pd.Series) -> float:
    """Most negative peak-to-trough decline over the series, in percent."""
    running_max = series.cummax()
    drawdown = (series - running_max) / running_max
    return float(drawdown.min() * 100.0)


def downside_deviation(returns: pd.Series, target: float = 0.0) -> float:
    """Annualized standard deviation of below-target returns only."""
    downside = returns[returns < target]
    if len(downside) < 2:
        return float("nan")
    return float(downside.std() * np.sqrt(TRADING_DAYS_PER_YEAR) * 100.0)
