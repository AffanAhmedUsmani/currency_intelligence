"""The Buying Opportunity Engine.

Combines seven independently-computed signals into a single 0-100 score
using the weighted framework proposed in the product brief. The brief is
explicit that these weights are "initial hypotheses, not established
truths" — `backtest.py` is what actually checks whether this scoring
produces signals with any historical value; this module does not claim
validated predictive power on its own, only a transparent, inspectable
combination of evidence.

Each component is scored 0-100 where higher = more supportive of "this is
worth considering as a buying opportunity right now". 50 is neutral/unknown.
"""

from dataclasses import dataclass, field

import numpy as np

from app.analytics.meanreversion import MeanReversionResult
from app.analytics.trend import TrendResult
from app.analytics.forecast import ForecastResult
from app.analytics.volatility import volatility_regime

WEIGHTS = {
    "valuation_deviation": 0.20,
    "short_term_decline": 0.15,
    "mean_reversion": 0.15,
    "momentum_improvement": 0.15,
    "trend_confirmation": 0.10,
    "volatility_risk": 0.10,
    "probabilistic_forecast": 0.10,
    "data_quality": 0.05,
}


@dataclass
class ComponentScores:
    valuation_deviation: float
    short_term_decline: float
    mean_reversion: float
    momentum_improvement: float
    trend_confirmation: float
    volatility_risk: float
    probabilistic_forecast: float
    data_quality: float


@dataclass
class OpportunityResult:
    score: float
    classification: str
    components: ComponentScores
    supporting_signals: list[str] = field(default_factory=list)
    contradicting_signals: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    invalidation_conditions: list[str] = field(default_factory=list)
    summary: str = ""


def _clip(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return float(max(lo, min(hi, x)))


def score_valuation_deviation(zscore: float | None) -> float:
    """zscore is on the base->quote RATE series (quote units per 1 base
    unit). A POSITIVE zscore means the rate is currently elevated versus
    its own recent history — i.e. 1 base-currency unit currently buys MORE
    of the quote currency than usual, which means the quote currency is
    currently CHEAP relative to its own history. That is the buy-favorable
    direction, so positive zscore must score HIGH, not low. (Verified
    empirically in tests/test_scoring.py: a positive-zscore entry point
    measurably precedes positive value returns on synthetic mean-reverting
    data, and the reverse for negative zscore.)
    """
    if zscore is None:
        return 50.0
    return _clip(50.0 + zscore * 15.0)


def score_short_term_decline(pct_change: float | None) -> float:
    """pct_change is the RATE's own % change (quote units per base unit).
    A POSITIVE pct_change means the rate rose, i.e. the quote currency got
    CHEAPER over the period — the favorable direction for a prospective
    buyer, so it must score HIGH, not low. (See score_valuation_deviation's
    docstring for the full derivation; this is the same rate/value
    distinction, just on recent price change instead of z-score.)
    """
    if pct_change is None or np.isnan(pct_change):
        return 50.0
    return _clip(50.0 + pct_change * 3.0)


def score_mean_reversion(mr: MeanReversionResult) -> float:
    """Same direction as score_valuation_deviation: when reversion is
    statistically supported, a positive zscore (rate currently elevated,
    quote currency currently cheap) implies reversion will pull the rate
    back down — i.e. the quote currency getting *more* expensive again —
    which is exactly the "buy while it's cheap, before it reverts" case.
    """
    if not mr.is_statistically_supported or mr.zscore is None:
        return 40.0
    return _clip(50.0 + mr.zscore * 20.0)


def score_momentum_improvement(trend: TrendResult, rsi_latest: float | None) -> float:
    base = {
        "accelerating_down": 15.0,
        "decelerating_down": 70.0,
        "flat": 50.0,
        "decelerating_up": 55.0,
        "accelerating_up": 35.0,
        "unknown": 50.0,
    }.get(trend.momentum_state, 50.0)
    if rsi_latest is not None and not np.isnan(rsi_latest):
        if rsi_latest < 30:
            base += 10.0
        elif rsi_latest > 70:
            base -= 10.0
    return _clip(base)


def score_trend_confirmation(trend: TrendResult) -> float:
    if trend.reversal_signal == "bullish_crossover":
        return 80.0
    if trend.reversal_signal == "bearish_crossover":
        return 20.0
    return {"uptrend": 65.0, "sideways": 50.0, "downtrend": 30.0, "unknown": 50.0}.get(
        trend.direction, 50.0
    )


def score_volatility_risk(vol_percentile: float | None) -> float:
    if vol_percentile is None:
        return 50.0
    return _clip(100.0 - vol_percentile)


def score_probabilistic_forecast(forecast: ForecastResult) -> float:
    """`forecast.prob_appreciation`/`prob_depreciation` describe the base->quote
    RATE's own simulated direction (see forecast.py), reused as-is by the
    calculator's "if you wait to convert" scenarios where a rising rate is
    genuinely the favorable outcome. For a buy-opportunity score, the
    favorable outcome is the RATE FALLING after purchase (quote currency
    getting more expensive, i.e. appreciating in value) — that's
    `prob_depreciation` of the rate, not `prob_appreciation` of it.
    """
    if forecast.confidence == "insufficient_data" or forecast.prob_depreciation is None:
        return 50.0
    return _clip(forecast.prob_depreciation)


def score_data_quality(
    zscore: float | None,
    forecast: ForecastResult,
    trend: TrendResult,
    n_observations: int,
    min_observations: int,
) -> float:
    checks = [
        zscore is not None,
        forecast.confidence != "insufficient_data",
        trend.direction != "unknown",
        n_observations >= min_observations,
    ]
    return _clip(sum(checks) / len(checks) * 100.0)


def classify(score: float, risk_score: float, data_quality: float) -> str:
    if data_quality < 35:
        return "WAIT / MONITOR"
    if risk_score < 20 and score >= 58:
        # Looks attractive on paper but downside risk is unusually elevated — don't call it a buy.
        return "WAIT / MONITOR"
    if score >= 72 and risk_score >= 35:
        return "STRONG BUY OPPORTUNITY"
    if score >= 58:
        return "POTENTIAL BUY"
    if score >= 45:
        return "WAIT / MONITOR"
    if score >= 32:
        return "HOLD / NEUTRAL"
    return "AVOID FOR NOW"


def compute_opportunity(
    *,
    code: str,
    pct_change: float | None,
    zscore: float | None,
    mean_reversion: MeanReversionResult,
    trend: TrendResult,
    rsi_latest: float | None,
    vol_percentile: float | None,
    forecast: ForecastResult,
    n_observations: int,
    min_observations: int,
) -> OpportunityResult:
    c = ComponentScores(
        valuation_deviation=score_valuation_deviation(zscore),
        short_term_decline=score_short_term_decline(pct_change),
        mean_reversion=score_mean_reversion(mean_reversion),
        momentum_improvement=score_momentum_improvement(trend, rsi_latest),
        trend_confirmation=score_trend_confirmation(trend),
        volatility_risk=score_volatility_risk(vol_percentile),
        probabilistic_forecast=score_probabilistic_forecast(forecast),
        data_quality=score_data_quality(zscore, forecast, trend, n_observations, min_observations),
    )

    score = (
        c.valuation_deviation * WEIGHTS["valuation_deviation"]
        + c.short_term_decline * WEIGHTS["short_term_decline"]
        + c.mean_reversion * WEIGHTS["mean_reversion"]
        + c.momentum_improvement * WEIGHTS["momentum_improvement"]
        + c.trend_confirmation * WEIGHTS["trend_confirmation"]
        + c.volatility_risk * WEIGHTS["volatility_risk"]
        + c.probabilistic_forecast * WEIGHTS["probabilistic_forecast"]
        + c.data_quality * WEIGHTS["data_quality"]
    )

    classification = classify(score, c.volatility_risk, c.data_quality)

    supporting, contradicting, risks, invalidation = _build_explanation(
        code, pct_change, zscore, mean_reversion, trend, vol_percentile, forecast, c
    )

    summary = _build_summary(code, pct_change, mean_reversion, trend, classification)

    return OpportunityResult(
        score=round(score, 1),
        classification=classification,
        components=c,
        supporting_signals=supporting,
        contradicting_signals=contradicting,
        risks=risks,
        invalidation_conditions=invalidation,
        summary=summary,
    )


def _build_explanation(code, pct_change, zscore, mr, trend, vol_percentile, forecast, c):
    supporting, contradicting, risks, invalidation = [], [], [], []

    # pct_change/zscore are on the base->quote RATE: the rate RISING means the quote
    # currency got CHEAPER (you get more of it per unit of base currency) — the
    # buy-favorable direction. See score_valuation_deviation's docstring for the derivation.
    if pct_change is not None and not np.isnan(pct_change):
        if pct_change > 1.5:
            supporting.append(f"{code} has gotten {pct_change:.1f}% cheaper against the base currency over the selected period.")
        elif pct_change < -1.5:
            contradicting.append(f"{code} has actually gotten {abs(pct_change):.1f}% more expensive over the selected period, not cheaper.")

    if zscore is not None:
        if zscore > 1.0:
            supporting.append(f"Currently {zscore:.1f} standard deviations cheaper than its recent average (unusually inexpensive vs. its own history).")
        elif zscore < -1.0:
            contradicting.append(f"Currently {abs(zscore):.1f} standard deviations more expensive than its recent average (unusually pricey vs. its own history).")

    if mr.is_statistically_supported:
        supporting.append("Historically, deviations like this one have tended to fade (statistically measurable mean reversion).")
    else:
        risks.append("No statistically reliable mean-reversion pattern was found — a low rate here is not guaranteed to recover.")

    if trend.momentum_state == "decelerating_down":
        supporting.append("The recent decline is losing speed — downward momentum appears to be stabilizing.")
    elif trend.momentum_state == "accelerating_down":
        contradicting.append("The decline is still accelerating — momentum has not yet stabilized.")

    if trend.reversal_signal == "bullish_crossover":
        supporting.append("A short-term moving average recently crossed above the longer-term average, an early trend-reversal signal.")
    elif trend.direction == "downtrend":
        risks.append("The longer-term trend remains negative.")

    if vol_percentile is not None and vol_percentile >= 70:
        risks.append(f"Volatility is elevated (higher than {vol_percentile:.0f}% of its own historical range) — moves in either direction could be larger than usual.")
    elif vol_percentile is not None and vol_percentile <= 30:
        supporting.append("Volatility is currently low relative to its own history.")

    if forecast.confidence != "insufficient_data" and forecast.prob_appreciation is not None:
        if forecast.prob_appreciation >= 55:
            supporting.append(f"Simulation based on historical patterns gives a {forecast.prob_appreciation:.0f}% chance of appreciation over the forecast horizon (weak evidence — see uncertainty range).")
        elif forecast.prob_appreciation <= 45:
            contradicting.append(f"Simulation based on historical patterns gives only a {forecast.prob_appreciation:.0f}% chance of appreciation over the forecast horizon.")
    else:
        risks.append("Insufficient history for a statistically meaningful forecast.")

    invalidation.append("A continued acceleration of the decline, or a break to a new multi-period low, would undermine this read.")
    invalidation.append("A reversal in the broader trend (e.g. a bearish moving-average crossover) would invalidate a bullish signal here.")

    return supporting, contradicting, risks, invalidation


def _build_summary(code, pct_change, mr, trend, classification) -> str:
    pct_txt = f"{abs(pct_change):.1f}%" if pct_change is not None and not np.isnan(pct_change) else "an unclear amount"
    # pct_change is on the base->quote RATE: rate rising means the quote currency got
    # CHEAPER (weaker against the base), rate falling means it got MORE expensive
    # (stronger) — the opposite of what "risen"/"declined" would suggest if read as
    # describing the rate's own direction, so the wording below describes the
    # currency's real-world value move, not the raw number's sign.
    direction_txt = "weakened" if (pct_change or 0) > 0 else "strengthened"
    reversion_txt = (
        "and this level is statistically unusual relative to its own recent history"
        if mr.is_statistically_supported
        else "though no reliable mean-reversion pattern supports an automatic recovery"
    )
    trend_txt = {
        "uptrend": "the broader trend is currently positive",
        "downtrend": "the broader trend remains negative",
        "sideways": "the broader trend is flat",
    }.get(trend.direction, "the broader trend is unclear")

    return (
        f"{code} has {direction_txt} {pct_txt} over the selected period, {reversion_txt}, and {trend_txt}. "
        f"Combined with momentum and risk signals, this currently reads as: {classification}."
    )
