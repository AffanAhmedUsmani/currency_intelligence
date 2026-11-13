from datetime import datetime

from fastapi import APIRouter, HTTPException

from app.analytics.forecast import simulate_holding_period_outcomes
from app.analytics.volatility import log_returns
from app.schemas import CalculatorRequest
from app.serializers import safe_float
from app.services.analysis_engine import PERIOD_DAYS, analyze_pair

router = APIRouter(prefix="/api/calculator", tags=["calculator"])

# Standard holding periods projected for every calculator request, reusing
# the same period codes as the rest of the app (see lib/format.ts PERIOD_LABELS
# on the frontend) so the UI can label them consistently.
HOLDING_PERIOD_HORIZONS = {k: PERIOD_DAYS[k] for k in ("14d", "1m", "3m", "6m", "1y")}


@router.post("")
async def calculate(req: CalculatorRequest):
    base, target = req.base.upper(), req.target.upper()
    if base == target:
        raise HTTPException(400, "Base and target currency must differ")

    analysis = await analyze_pair(base, target, req.comparison_period)
    if analysis.data_error and analysis.series_full.empty:
        raise HTTPException(502, analysis.data_error)

    rate = analysis.latest_rate
    fee_mult = 1 - (req.fee_pct / 100.0)
    received = req.amount * rate * fee_mult
    fee_cost_in_base = req.amount * (req.fee_pct / 100.0)

    display = analysis.series_display.dropna()
    period_high = float(display.max()) if len(display) else rate
    period_low = float(display.min()) if len(display) else rate
    period_avg = float(display.mean()) if len(display) else rate

    forecast = analysis.forecast
    opp = analysis.opportunity
    trend = analysis.trend

    def scenario(label: str, scenario_rate: float):
        scenario_received = req.amount * scenario_rate * fee_mult
        return {
            "label": label,
            "rate": safe_float(scenario_rate),
            "received_amount": safe_float(scenario_received),
            "diff_vs_current": safe_float(scenario_received - received),
        }

    scenarios = [
        scenario(f"If you wait, and the rate returns to this period's high ({period_high:.4f})", period_high),
        scenario(f"If you wait, and the rate falls to this period's low ({period_low:.4f})", period_low),
    ]
    if forecast and forecast.confidence != "insufficient_data" and forecast.ci_high_pct is not None:
        scenarios.append(
            scenario(
                f"If you wait — optimistic model scenario (95th percentile of simulated {forecast.horizon_days}-day outcomes)",
                rate * (1 + forecast.ci_high_pct / 100.0),
            )
        )
        scenarios.append(
            scenario(
                f"If you wait — pessimistic model scenario (5th percentile of simulated {forecast.horizon_days}-day outcomes)",
                rate * (1 + forecast.ci_low_pct / 100.0),
            )
        )

    returns = log_returns(analysis.series_full)
    holding_outcomes = simulate_holding_period_outcomes(
        returns, amount=req.amount, fee_pct=req.fee_pct, horizons_days=HOLDING_PERIOD_HORIZONS
    )
    holding_period_projections = [
        {
            "period": o.label,
            "horizon_days": o.horizon_days,
            "expected_value": safe_float(o.expected_value),
            "expected_profit_loss": safe_float(o.expected_profit_loss),
            "expected_profit_loss_pct": safe_float(o.expected_profit_loss_pct),
            "optimistic_value": safe_float(o.optimistic_value),
            "optimistic_profit_loss": safe_float(o.optimistic_profit_loss),
            "pessimistic_value": safe_float(o.pessimistic_value),
            "pessimistic_profit_loss": safe_float(o.pessimistic_profit_loss),
            "prob_profit_pct": safe_float(o.prob_profit_pct),
            "confidence": o.confidence,
            "note": o.note,
        }
        for o in holding_outcomes
    ]

    mr = analysis.mean_reversion
    # Rate is the app-wide base->quote convention: a HIGHER rate means the target
    # currency is CHEAPER (1 base-currency unit buys more of it). So "currently
    # expensive vs. history" is a NEGATIVE zscore, and "recently became cheaper"
    # is a POSITIVE pct_change — see scoring.py's score_valuation_deviation
    # docstring for the full derivation of this sign convention.
    decision_support = {
        "is_relatively_expensive_vs_history": bool(mr and mr.zscore is not None and mr.zscore < -0.5),
        "has_recently_become_cheaper": bool(analysis.pct_change is not None and analysis.pct_change > 0),
        "decline_losing_or_gaining_speed": trend.momentum_state if trend else "unknown",
        "showing_signs_of_recovery": bool(trend and trend.momentum_state == "decelerating_down" or (trend and trend.reversal_signal == "bullish_crossover")),
        "elevated_risk_of_further_moves": analysis.vol_regime in ("elevated", "high"),
        "recommendation": opp.classification if opp else "WAIT / MONITOR",
        "explanation": opp.summary if opp else "Insufficient data for a confident recommendation.",
    }

    return {
        "base": base,
        "target": target,
        "amount": req.amount,
        "fee_pct": req.fee_pct,
        "current_rate": safe_float(rate),
        "rate_kind": analysis.rate_kind,
        "provider": analysis.provider,
        "received_amount": safe_float(received),
        "fee_cost_in_base_currency": safe_float(fee_cost_in_base),
        "historical": {
            "period": req.comparison_period,
            "pct_change": safe_float(analysis.pct_change),
            "period_high": safe_float(period_high),
            "period_low": safe_float(period_low),
            "period_avg": safe_float(period_avg),
        },
        "scenarios": scenarios,
        "holding_period_projections": holding_period_projections,
        "decision_support": decision_support,
        "last_updated": datetime.utcnow().isoformat() + "Z",
        "disclaimer": (
            "This uses an indicative/reference mid-market rate, not a rate any specific exchange "
            "dealer will actually give you. Real-world conversions include dealer spreads and fees "
            "beyond what you entered here. Historical performance does not guarantee future results."
        ),
    }
