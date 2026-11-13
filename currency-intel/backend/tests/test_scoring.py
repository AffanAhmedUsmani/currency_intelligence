import numpy as np
import pandas as pd

from app.analytics import scoring as sc
from app.analytics.meanreversion import MeanReversionResult
from app.analytics.trend import TrendResult
from app.analytics.forecast import ForecastResult


def _trend(**overrides):
    base = dict(direction="downtrend", momentum_state="decelerating_down", reversal_signal=None, short_vs_long_pct=-1.0)
    base.update(overrides)
    return TrendResult(**base)


def _mr(**overrides):
    base = dict(zscore=-1.5, bollinger_position=0.1, ar1_coefficient=0.7, half_life_days=10.0,
                is_statistically_supported=True, note="")
    base.update(overrides)
    return MeanReversionResult(**base)


def _forecast(**overrides):
    base = dict(horizon_days=30, expected_pct_move=1.0, prob_appreciation=60.0, prob_depreciation=40.0,
                ci_low_pct=-5.0, ci_high_pct=7.0, method="bootstrap_monte_carlo", confidence="medium",
                secondary_trend_pct=None, note="")
    base.update(overrides)
    return ForecastResult(**base)


def test_classify_strong_buy_requires_high_score_and_acceptable_risk():
    assert sc.classify(score=80, risk_score=50, data_quality=80) == "STRONG BUY OPPORTUNITY"


def test_classify_caps_at_wait_when_data_quality_low():
    assert sc.classify(score=90, risk_score=90, data_quality=10) == "WAIT / MONITOR"


def test_classify_caps_at_wait_when_risk_extreme_even_with_high_score():
    assert sc.classify(score=60, risk_score=5, data_quality=80) == "WAIT / MONITOR"


def test_classify_avoid_for_low_score():
    assert sc.classify(score=10, risk_score=50, data_quality=80) == "AVOID FOR NOW"


def test_compute_opportunity_produces_bounded_score_and_explanation():
    result = sc.compute_opportunity(
        code="AUD",
        pct_change=-4.0,
        zscore=-1.8,
        mean_reversion=_mr(),
        trend=_trend(),
        rsi_latest=28.0,
        vol_percentile=70.0,
        forecast=_forecast(),
        n_observations=120,
        min_observations=30,
    )
    assert 0 <= result.score <= 100
    assert result.classification in {
        "STRONG BUY OPPORTUNITY", "POTENTIAL BUY", "WAIT / MONITOR", "HOLD / NEUTRAL", "AVOID FOR NOW",
    }
    assert result.summary
    assert isinstance(result.supporting_signals, list)


# --- Direction tests -------------------------------------------------------
#
# The series everywhere in this app is the base->quote RATE (quote units per
# 1 base unit). A RISING rate means the quote currency got CHEAPER (you get
# more of it per unit of base currency than before) — that is the
# buy-favorable direction, not "the currency declined". These tests pin that
# direction down explicitly component-by-component, because an earlier
# version of this file asserted the opposite (a test named
# "rising_currency_does_not_get_treated_as_decline_opportunity" that actually
# encoded the rate/value sign confusion as if it were correct behavior) and
# passed anyway, which is exactly how the bug went undetected: the test was
# validating a wrong mental model instead of the real one. It was only
# caught when a later, independent walk-forward backtest of currency
# selection (tests/test_weekly_rotation_backtest.py) failed on synthetic
# data where the correct direction was externally known.

def test_valuation_score_favors_positive_zscore_cheap_currency():
    assert sc.score_valuation_deviation(zscore=2.0) > 50.0
    assert sc.score_valuation_deviation(zscore=-2.0) < 50.0
    assert sc.score_valuation_deviation(zscore=None) == 50.0


def test_short_term_decline_score_favors_rate_that_rose_currency_cheapened():
    assert sc.score_short_term_decline(pct_change=4.0) > 50.0
    assert sc.score_short_term_decline(pct_change=-4.0) < 50.0


def test_mean_reversion_score_favors_positive_zscore_when_supported():
    assert sc.score_mean_reversion(_mr(zscore=2.0, is_statistically_supported=True)) > 50.0
    assert sc.score_mean_reversion(_mr(zscore=-2.0, is_statistically_supported=True)) < 50.0
    # Unsupported reversion is treated as a mild negative regardless of zscore sign.
    assert sc.score_mean_reversion(_mr(zscore=2.0, is_statistically_supported=False)) == 40.0


def test_probabilistic_forecast_score_uses_depreciation_not_appreciation_of_rate():
    """A buy-favorable forecast is one where the RATE is expected to fall
    (quote currency appreciates in value) — that's prob_depreciation of the
    rate series, not prob_appreciation of it."""
    favorable = sc.score_probabilistic_forecast(_forecast(prob_appreciation=30.0, prob_depreciation=70.0))
    unfavorable = sc.score_probabilistic_forecast(_forecast(prob_appreciation=70.0, prob_depreciation=30.0))
    assert favorable > 50.0
    assert unfavorable < 50.0


def test_strengthening_currency_does_not_get_treated_as_a_bargain():
    """pct_change < 0 means the rate FELL, i.e. the currency got MORE
    expensive (stronger) against the base currency — the opposite of a
    bargain. Valuation and short-term-decline components must score below
    neutral, not above it."""
    result = sc.compute_opportunity(
        code="XYZ",
        pct_change=-5.0,
        zscore=-1.8,
        mean_reversion=_mr(zscore=-1.8, is_statistically_supported=False),
        trend=_trend(direction="downtrend", momentum_state="accelerating_down", reversal_signal=None),
        rsi_latest=20.0,
        vol_percentile=70.0,
        forecast=_forecast(prob_appreciation=70.0, prob_depreciation=30.0),
        n_observations=120,
        min_observations=30,
    )
    assert result.components.valuation_deviation < 50
    assert result.components.short_term_decline < 50


def test_cheapening_currency_is_treated_as_a_genuine_bargain():
    """pct_change > 0 means the rate ROSE, i.e. the currency got CHEAPER
    against the base currency — a real bargain-favorable signal, and the
    core valuation components should score above neutral for it."""
    result = sc.compute_opportunity(
        code="AUD",
        pct_change=4.0,
        zscore=1.8,
        mean_reversion=_mr(zscore=1.8, is_statistically_supported=True),
        trend=_trend(direction="uptrend", momentum_state="decelerating_up", reversal_signal=None),
        rsi_latest=70.0,
        vol_percentile=40.0,
        forecast=_forecast(prob_appreciation=40.0, prob_depreciation=60.0),
        n_observations=120,
        min_observations=30,
    )
    assert result.components.valuation_deviation > 50
    assert result.components.short_term_decline > 50
    assert result.components.mean_reversion > 50
