"""Mean-reversion analysis.

Important caveat baked into this module (per the product brief): FX rates
are not guaranteed to be mean-reverting. Many exchange rates behave close to
a random walk, or trend persistently for fundamental reasons (sustained
inflation differentials, structural current-account deficits, etc.). This
module therefore always reports whether mean-reversion is *statistically
supported* for the given series, not just a z-score in isolation — a large
z-score on a trending series is a warning sign, not a buy signal.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class MeanReversionResult:
    zscore: float | None
    bollinger_position: float | None  # 0 = lower band, 0.5 = mid, 1 = upper band
    ar1_coefficient: float | None  # AR(1) coefficient on deviations from rolling mean
    half_life_days: float | None
    is_statistically_supported: bool
    note: str


def rolling_zscore(series: pd.Series, window: int) -> pd.Series:
    mean = series.rolling(window=window, min_periods=window).mean()
    std = series.rolling(window=window, min_periods=window).std()
    return (series - mean) / std.replace(0, np.nan)


def bollinger_position(series: pd.Series, mid: pd.Series, upper: pd.Series, lower: pd.Series) -> pd.Series:
    band_width = (upper - lower).replace(0, np.nan)
    return (series - lower) / band_width


def _ar1_half_life(series: pd.Series, window: int) -> tuple[float | None, float | None, bool]:
    """Fits y_t - mean = phi * (y_{t-1} - mean) + eps via OLS on the trailing
    window, and derives a half-life from phi. Flags statistical support only
    when 0 < phi < 1 with a plausible t-stat, i.e. genuine reversion rather
    than a random walk (phi ~ 1) or explosive/alternating series.
    """
    recent = series.tail(window).dropna()
    if len(recent) < 15:
        return None, None, False

    mean = recent.mean()
    y = (recent - mean).to_numpy()
    y_lag, y_now = y[:-1], y[1:]
    if np.allclose(y_lag.std(), 0):
        return None, None, False

    # Simple OLS for phi: y_now = phi * y_lag + eps
    phi = float(np.dot(y_lag, y_now) / np.dot(y_lag, y_lag))
    residuals = y_now - phi * y_lag
    n = len(y_lag)
    if n < 10:
        return phi, None, False
    resid_std = residuals.std(ddof=2)
    se_phi = resid_std / (np.sqrt(np.dot(y_lag, y_lag)) + 1e-12)
    t_stat = phi / se_phi if se_phi > 0 else 0.0

    supported = bool((0 < phi < 0.98) and abs(t_stat) > 2.0)
    half_life = None
    if phi > 0 and phi < 1:
        half_life = float(np.log(0.5) / np.log(phi)) if phi > 0 else None
    return phi, half_life, supported


def analyze(
    series: pd.Series,
    mid: pd.Series,
    upper: pd.Series,
    lower: pd.Series,
    zscore_window: int = 30,
    ar_window: int = 90,
) -> MeanReversionResult:
    z = rolling_zscore(series, zscore_window)
    pos = bollinger_position(series, mid, upper, lower)
    phi, half_life, supported = _ar1_half_life(series, min(ar_window, len(series)))

    latest_z = float(z.iloc[-1]) if not z.empty and not np.isnan(z.iloc[-1]) else None
    latest_pos = float(pos.iloc[-1]) if not pos.empty and not np.isnan(pos.iloc[-1]) else None

    if supported:
        note = (
            "This currency's recent moves relative to its own average show a statistically "
            "measurable tendency to snap back — deviations from the mean have historically "
            "faded, not persisted."
        )
    else:
        note = (
            "No statistically reliable mean-reversion pattern was found for this pair over "
            "this window. A low current rate here should not be assumed to automatically "
            "recover — treat any apparent discount with extra caution."
        )

    return MeanReversionResult(
        zscore=latest_z,
        bollinger_position=latest_pos,
        ar1_coefficient=phi,
        half_life_days=half_life,
        is_statistically_supported=supported,
        note=note,
    )
