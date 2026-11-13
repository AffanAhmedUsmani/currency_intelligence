import numpy as np
import pandas as pd
import pytest

from app.analytics.weekly_rotation_backtest import (
    _max_drawdown_from_period_returns,
    backtest_weekly_rotation,
)


def _mean_reverting_series(n, mean=100.0, speed=0.06, noise=0.8, seed=0):
    rng = np.random.default_rng(seed)
    x = mean
    vals = []
    for _ in range(n):
        x = x + speed * (mean - x) + rng.normal(0, noise)
        vals.append(x)
    idx = pd.date_range("2023-01-01", periods=n, freq="D")
    return pd.Series(vals, index=idx)


def _random_walk_series(n, start=100.0, noise=0.8, seed=1):
    rng = np.random.default_rng(seed)
    vals = start + np.cumsum(rng.normal(0, noise, n))
    idx = pd.date_range("2023-01-01", periods=n, freq="D")
    return pd.Series(vals, index=idx)


def test_strategy_beats_benchmark_when_mean_reversion_is_genuine():
    """If several candidates are engineered to be strongly mean-reverting
    (a dip is reliably followed by a bounce) and the rest are pure noise,
    picking the most-negative-z-score names every period should pick up
    on that and beat equally diversifying across everyone."""
    n = 500
    series = {}
    for i in range(4):
        series[f"MR{i}"] = _mean_reverting_series(n, speed=0.08, noise=1.0, seed=100 + i)
    for i in range(4):
        series[f"RW{i}"] = _random_walk_series(n, noise=1.0, seed=200 + i)

    result = backtest_weekly_rotation(series, top_n=2, rebalance_days=7, zscore_window=20)

    assert result.n_checkpoints >= 20
    assert result.beats_benchmark is True
    assert result.strategy_cumulative_return_pct > result.benchmark_cumulative_return_pct


def test_selected_currencies_are_the_most_positive_zscore_at_checkpoint():
    """Positive z-score = rate currently elevated vs its own history = the quote
    currency is currently cheap (buys more of it per base-currency unit than
    usual) — the buy-favorable direction. See scoring.py's
    score_valuation_deviation docstring for the full derivation."""
    n = 300
    series = {f"C{i}": _random_walk_series(n, noise=1.0, seed=300 + i) for i in range(6)}
    result = backtest_weekly_rotation(series, top_n=2, rebalance_days=7, zscore_window=20)
    assert result.n_checkpoints > 0

    from app.analytics.meanreversion import rolling_zscore

    df = pd.DataFrame(series).sort_index()
    zscores = pd.DataFrame({c: rolling_zscore(df[c], 20) for c in df.columns})

    for period in result.periods[:5]:
        t = df.index.get_loc(pd.Timestamp(period.date))
        row_z = zscores.iloc[t].dropna().sort_values(ascending=False)
        expected_top2 = list(row_z.index[:2])
        assert period.selected == expected_top2


def test_no_lookahead_truncated_history_gives_identical_early_periods():
    """Extending the series with MORE future data must not change the
    selections or returns already computed for earlier checkpoints."""
    n_full = 400
    series_full = {f"C{i}": _random_walk_series(n_full, noise=1.0, seed=400 + i) for i in range(6)}

    n_short = 250  # still covers at least MIN_CHECKPOINTS periods
    series_short = {code: s.iloc[:n_short] for code, s in series_full.items()}

    result_full = backtest_weekly_rotation(series_full, top_n=2, rebalance_days=7, zscore_window=20)
    result_short = backtest_weekly_rotation(series_short, top_n=2, rebalance_days=7, zscore_window=20)

    assert result_short.n_checkpoints > 0
    overlap = min(len(result_full.periods), len(result_short.periods))
    assert overlap >= 10

    for i in range(overlap):
        assert result_full.periods[i].date == result_short.periods[i].date
        assert result_full.periods[i].selected == result_short.periods[i].selected
        assert result_full.periods[i].strategy_return_pct == pytest.approx(
            result_short.periods[i].strategy_return_pct, abs=1e-9
        )


def test_fee_reduces_both_strategy_and_benchmark_cumulative_return():
    n = 400
    series = {f"C{i}": _random_walk_series(n, noise=1.0, seed=500 + i) for i in range(6)}
    no_fee = backtest_weekly_rotation(series, top_n=2, rebalance_days=7, zscore_window=20, fee_pct=0.0)
    with_fee = backtest_weekly_rotation(series, top_n=2, rebalance_days=7, zscore_window=20, fee_pct=2.0)
    assert with_fee.strategy_cumulative_return_pct < no_fee.strategy_cumulative_return_pct
    assert with_fee.benchmark_cumulative_return_pct < no_fee.benchmark_cumulative_return_pct


def test_insufficient_data_is_explicit_not_a_crash():
    series = {f"C{i}": _random_walk_series(40, seed=600 + i) for i in range(4)}
    result = backtest_weekly_rotation(series, top_n=2, rebalance_days=7, zscore_window=20)
    assert result.n_checkpoints == 0
    assert "Not enough" in result.note
    assert result.strategy_sharpe_like is None


def test_too_few_candidates_for_top_n_is_explicit():
    series = {f"C{i}": _random_walk_series(500, seed=700 + i) for i in range(2)}
    result = backtest_weekly_rotation(series, top_n=3, rebalance_days=7, zscore_window=20)
    assert result.n_checkpoints == 0
    assert "Not enough" in result.note


def test_max_drawdown_matches_manual_calculation():
    returns = [10.0, -20.0, 5.0, -10.0, 15.0]
    # equity: 1.10, 0.88, 0.924, 0.8316, 0.95634
    # running max: 1.10, 1.10, 1.10, 1.10, 1.10
    # drawdown: 0, -0.2, -0.16, -0.244, -0.1306...
    dd = _max_drawdown_from_period_returns(returns)
    assert dd == pytest.approx(-24.4, abs=0.1)


def test_max_drawdown_empty_is_zero():
    assert _max_drawdown_from_period_returns([]) == 0.0
