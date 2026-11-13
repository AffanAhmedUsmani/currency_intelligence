import numpy as np
import pandas as pd

from app.analytics.backtest import run_backtest


def _mean_reverting_series(n=500, seed=0):
    """Synthetic Ornstein-Uhlenbeck-like series that is deliberately
    engineered to mean-revert, so the backtest should find the z-score
    signal has genuine predictive value on this synthetic case."""
    rng = np.random.default_rng(seed)
    mean = 100.0
    x = mean
    values = []
    for _ in range(n):
        x = x + 0.08 * (mean - x) + rng.normal(0, 1.0)
        values.append(x)
    idx = pd.date_range("2022-01-01", periods=n, freq="D")
    return pd.Series(values, index=idx)


def _random_walk_series(n=500, seed=1):
    rng = np.random.default_rng(seed)
    steps = rng.normal(0, 1.0, n)
    values = 100.0 + np.cumsum(steps)
    idx = pd.date_range("2022-01-01", periods=n, freq="D")
    return pd.Series(values, index=idx)


def test_backtest_detects_edge_on_synthetic_mean_reverting_series():
    series = _mean_reverting_series()
    result = run_backtest(series, horizon_days=10, z_window=20, entry_threshold=1.0)
    assert result.n_signals > 5
    assert result.signal_hit_rate_pct > result.baseline_hit_rate_pct
    assert result.beats_baseline is True


def test_backtest_on_pure_random_walk_does_not_fabricate_confidence():
    series = _random_walk_series()
    result = run_backtest(series, horizon_days=10, z_window=20, entry_threshold=1.0)
    # On a true random walk we make no claim either way about whether it beats baseline,
    # but it must not crash and must return a well-formed, bounded result.
    assert result.n_baseline_days > 0
    if result.signal_hit_rate_pct is not None:
        assert 0 <= result.signal_hit_rate_pct <= 100
    assert result.brier_score is None or 0 <= result.brier_score <= 1


def test_baseline_return_direction_for_a_steadily_rising_rate():
    """A steadily RISING rate means the quote currency is steadily getting
    CHEAPER (you get more of it per base-currency unit over time) — buying
    now and converting back later should show a NEGATIVE value return
    throughout. Confirms forward_return_pct uses now/future (holding
    value), not future/now (raw rate change)."""
    n = 100
    idx = pd.date_range("2022-01-01", periods=n)
    rising_rate = pd.Series(100 + np.arange(n) * 0.5, index=idx)
    result = run_backtest(rising_rate, horizon_days=10, z_window=20)
    assert result.avg_baseline_return_pct is not None
    assert result.avg_baseline_return_pct < 0


def test_backtest_insufficient_data_is_explicit():
    series = pd.Series([100.0, 101.0, 99.0], index=pd.date_range("2024-01-01", periods=3))
    result = run_backtest(series)
    assert result.signal_hit_rate_pct is None
    assert "Not enough" in result.note
