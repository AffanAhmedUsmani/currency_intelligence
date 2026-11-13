import numpy as np
import pandas as pd
import pytest

from app.analytics.portfolio import build_portfolio


def _series(mean, std, n=200, seed=0, corr_with=None, corr=0.0):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2024-01-01", periods=n, freq="D")
    if corr_with is None:
        vals = rng.normal(mean, std, n)
    else:
        base = corr_with
        noise = rng.normal(0, std, n)
        vals = mean + corr * (base - base.mean()) / base.std() * std + np.sqrt(1 - corr ** 2) * noise
    return pd.Series(vals, index=idx)


def test_two_independent_assets_diversify_below_either_individual_volatility():
    a = _series(mean=0.0, std=0.01, seed=1)
    b = _series(mean=0.0, std=0.01, seed=2)
    result = build_portfolio({"A": a, "B": b}, amount=100_000, fee_pct=0.0, horizon_days=30, target_return_pct=None)
    individual_vol = result.allocation[0].individual_volatility_pct
    assert result.analytic_volatility_pct < individual_vol * 0.95  # real diversification benefit


def test_perfectly_correlated_assets_flag_a_warning_and_give_no_diversification():
    a = _series(mean=0.0, std=0.01, seed=3)
    b = a + 0.0  # identical series => correlation 1.0
    result = build_portfolio({"A": a, "B": b}, amount=100_000, fee_pct=0.0, horizon_days=30, target_return_pct=None)
    assert len(result.correlation_warnings) == 1
    assert "A" in result.correlation_warnings[0] and "B" in result.correlation_warnings[0]
    # No diversification benefit: portfolio vol should roughly equal either individual's vol.
    assert result.analytic_volatility_pct == pytest.approx(result.allocation[0].individual_volatility_pct, rel=0.05)


def test_target_return_above_achievable_max_is_clamped():
    a = _series(mean=0.0005, std=0.01, seed=4)
    b = _series(mean=-0.0003, std=0.01, seed=5)
    result = build_portfolio({"A": a, "B": b}, amount=100_000, fee_pct=0.0, horizon_days=30, target_return_pct=9999.0)
    assert result.was_clamped is True
    assert result.effective_target_return_pct == pytest.approx(result.achievable_return_max_pct, abs=0.01)


def test_allocation_amounts_sum_to_total():
    a = _series(mean=0.0002, std=0.008, seed=6)
    b = _series(mean=-0.0001, std=0.012, seed=7)
    c = _series(mean=0.0001, std=0.006, seed=8)
    result = build_portfolio({"A": a, "B": b, "C": c}, amount=200_000, fee_pct=1.5, horizon_days=90, target_return_pct=None)
    total = sum(entry.amount for entry in result.allocation)
    assert total == pytest.approx(200_000, abs=0.01)
    assert {e.code for e in result.allocation} == {"A", "B", "C"}


def test_portfolio_outcome_direction_matches_weighted_drift():
    """If the base->target rate consistently FALLS (target appreciating, good for
    a holder), the simulated portfolio outcome should skew toward profit."""
    a = _series(mean=-0.003, std=0.004, seed=9)  # rate falling => target appreciating
    b = _series(mean=-0.0025, std=0.004, seed=10)
    result = build_portfolio({"A": a, "B": b}, amount=100_000, fee_pct=0.0, horizon_days=60, target_return_pct=None)
    assert result.outcome.expected_profit_loss > 0
    assert result.outcome.prob_profit_pct > 50


def test_minimum_variance_portfolio_has_the_lowest_risk_of_any_target():
    """The defining property of the mean-variance frontier: the min-variance
    portfolio's risk is <= the risk of a portfolio built for ANY other
    target return, in either direction. (The frontier is a parabola with
    its vertex at the min-variance point — moving the target away from the
    vertex in either direction can only add risk, never remove it.)"""
    a = _series(mean=0.0, std=0.006, seed=11)
    b = _series(mean=0.0, std=0.006, seed=15)
    c = _series(mean=0.003, std=0.02, seed=16)
    baseline = build_portfolio({"A": a, "B": b, "C": c}, amount=100_000, fee_pct=0.0, horizon_days=60, target_return_pct=None)
    lo, hi = baseline.achievable_return_min_pct, baseline.achievable_return_max_pct
    for frac in (0.05, 0.3, 0.7, 0.95):
        other = build_portfolio({"A": a, "B": b, "C": c}, amount=100_000, fee_pct=0.0, horizon_days=60, target_return_pct=lo + frac * (hi - lo))
        assert other.analytic_volatility_pct >= baseline.analytic_volatility_pct - 1e-6


def test_higher_target_above_the_min_variance_return_requires_more_risk():
    """The practical UX guarantee: once you ask for MORE than the safe
    (min-variance) baseline's own expected return, pushing the target up
    further should keep pushing risk up too — this is the "efficient"
    upper branch of the frontier, which is what a user dragging a target
    slider above the default actually moves along."""
    a = _series(mean=0.0, std=0.006, seed=11)
    b = _series(mean=0.0, std=0.006, seed=15)
    c = _series(mean=0.003, std=0.02, seed=16)
    baseline = build_portfolio({"A": a, "B": b, "C": c}, amount=100_000, fee_pct=0.0, horizon_days=60, target_return_pct=None)
    safe_return, hi = baseline.effective_target_return_pct, baseline.achievable_return_max_pct
    moderate = build_portfolio({"A": a, "B": b, "C": c}, amount=100_000, fee_pct=0.0, horizon_days=60, target_return_pct=safe_return + 0.3 * (hi - safe_return))
    aggressive = build_portfolio({"A": a, "B": b, "C": c}, amount=100_000, fee_pct=0.0, horizon_days=60, target_return_pct=safe_return + 0.8 * (hi - safe_return))
    assert aggressive.effective_target_return_pct > moderate.effective_target_return_pct > safe_return
    assert aggressive.analytic_volatility_pct > moderate.analytic_volatility_pct > baseline.analytic_volatility_pct


def test_target_return_is_actually_achieved_by_the_optimizer():
    a = _series(mean=0.0005, std=0.008, seed=13)
    b = _series(mean=-0.0003, std=0.01, seed=14)
    result = build_portfolio({"A": a, "B": b}, amount=100_000, fee_pct=0.0, horizon_days=45, target_return_pct=None)
    midpoint = (result.achievable_return_min_pct + result.achievable_return_max_pct) / 2
    targeted = build_portfolio({"A": a, "B": b}, amount=100_000, fee_pct=0.0, horizon_days=45, target_return_pct=midpoint)
    assert targeted.effective_target_return_pct == pytest.approx(midpoint, abs=0.05)


def test_insufficient_overlap_raises():
    a = pd.Series([0.001, -0.002], index=pd.date_range("2024-01-01", periods=2))
    b = pd.Series([0.001, -0.002], index=pd.date_range("2024-01-01", periods=2))
    with pytest.raises(ValueError):
        build_portfolio({"A": a, "B": b}, amount=100_000, fee_pct=0.0, horizon_days=30, target_return_pct=None)
