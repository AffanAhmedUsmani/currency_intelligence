import numpy as np
import pandas as pd

from app.analytics.forecast import simulate_holding_period_outcomes


def _returns(drift: float, n=250, seed=0):
    rng = np.random.default_rng(seed)
    vals = rng.normal(drift, 0.003, n)
    idx = pd.date_range("2024-01-01", periods=n, freq="D")
    return pd.Series(vals, index=idx)


def test_holding_period_breakeven_with_zero_drift_and_zero_fee():
    """If the base->target rate has no historical drift and there's no fee,
    the round trip should be a wash in expectation (median profit ~ 0)."""
    returns = _returns(drift=0.0)
    results = simulate_holding_period_outcomes(returns, amount=100_000, fee_pct=0.0, horizons_days={"1m": 30})
    r = results[0]
    assert r.expected_profit_loss is not None
    assert abs(r.expected_profit_loss) < 100_000 * 0.05  # within 5% of break-even, not systematically biased


def test_holding_period_loses_when_rate_trends_up_target_gets_cheaper():
    """If base->target rate (target units per base unit) consistently RISES,
    the target currency is getting cheaper over time — holding it and
    converting back later should show a projected loss."""
    returns = _returns(drift=0.004)  # rate drifting up => target getting cheaper
    results = simulate_holding_period_outcomes(returns, amount=100_000, fee_pct=0.0, horizons_days={"3m": 90})
    r = results[0]
    assert r.expected_profit_loss < 0
    assert r.prob_profit_pct < 50


def test_holding_period_gains_when_rate_trends_down_target_gets_pricier():
    """If base->target rate consistently FALLS, the target currency is
    getting more expensive (appreciating) — holding it should show a gain."""
    returns = _returns(drift=-0.004)
    results = simulate_holding_period_outcomes(returns, amount=100_000, fee_pct=0.0, horizons_days={"3m": 90})
    r = results[0]
    assert r.expected_profit_loss > 0
    assert r.prob_profit_pct > 50


def test_holding_period_fee_reduces_expected_value():
    returns = _returns(drift=0.0)
    no_fee = simulate_holding_period_outcomes(returns, amount=100_000, fee_pct=0.0, horizons_days={"1m": 30})[0]
    with_fee = simulate_holding_period_outcomes(returns, amount=100_000, fee_pct=2.0, horizons_days={"1m": 30})[0]
    assert with_fee.expected_value < no_fee.expected_value


def test_holding_period_insufficient_data_is_explicit():
    short_returns = pd.Series([0.001, -0.002, 0.0005], index=pd.date_range("2024-01-01", periods=3))
    results = simulate_holding_period_outcomes(short_returns, amount=100_000, fee_pct=1.0, horizons_days={"1m": 30})
    assert results[0].confidence == "insufficient_data"
    assert results[0].expected_profit_loss is None
