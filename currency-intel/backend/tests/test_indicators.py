import numpy as np
import pandas as pd
import pytest

from app.analytics import indicators as ind
from app.analytics import volatility as vol


def _series(values):
    idx = pd.date_range("2024-01-01", periods=len(values), freq="D")
    return pd.Series(values, index=idx, dtype=float)


def test_sma_matches_manual_mean():
    s = _series([1, 2, 3, 4, 5])
    result = ind.sma(s, 3)
    assert np.isnan(result.iloc[1])
    assert result.iloc[2] == pytest.approx(2.0)
    assert result.iloc[4] == pytest.approx(4.0)


def test_rsi_is_100_for_monotonic_increase():
    s = _series(list(range(1, 40)))
    r = ind.rsi(s, 14)
    assert r.dropna().iloc[-1] == pytest.approx(100.0, abs=1e-6)


def test_rsi_is_bounded():
    rng = np.random.default_rng(42)
    s = _series(100 + np.cumsum(rng.normal(0, 1, 100)))
    r = ind.rsi(s, 14).dropna()
    assert (r >= 0).all() and (r <= 100).all()


def test_macd_histogram_is_difference_of_lines():
    rng = np.random.default_rng(1)
    s = _series(100 + np.cumsum(rng.normal(0, 1, 60)))
    line, signal, hist = ind.macd(s)
    diff = (line - signal).dropna()
    hist_clean = hist.dropna()
    pd.testing.assert_series_equal(diff, hist_clean, check_names=False)


def test_bollinger_bands_bracket_sma():
    rng = np.random.default_rng(2)
    s = _series(100 + np.cumsum(rng.normal(0, 1, 60)))
    mid, upper, lower = ind.bollinger_bands(s, window=20)
    valid = mid.dropna().index
    assert (upper.loc[valid] >= mid.loc[valid]).all()
    assert (lower.loc[valid] <= mid.loc[valid]).all()


def test_max_drawdown_is_nonpositive():
    s = _series([100, 110, 90, 95, 80, 120])
    dd = vol.max_drawdown(s)
    assert dd <= 0
    assert dd == pytest.approx((80 - 110) / 110 * 100.0)


def test_log_returns_zero_for_constant_series():
    s = _series([50] * 10)
    r = vol.log_returns(s).dropna()
    assert (r.abs() < 1e-9).all()
