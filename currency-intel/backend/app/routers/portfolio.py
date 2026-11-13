import asyncio
from dataclasses import asdict
from datetime import date, timedelta

import pandas as pd
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.analytics import portfolio as port
from app.analytics.volatility import log_returns
from app.serializers import safe_float
from app.services import data_service
from app.services.analysis_engine import lookback_days_for, period_to_days
from app.services.currency_universe import get_meta

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


class PortfolioRequest(BaseModel):
    base: str
    targets: list[str] = Field(..., min_length=2, description="At least two target currencies")
    amount: float = Field(..., gt=0)
    fee_pct: float = Field(0.0, ge=0, le=20)
    holding_period: str = Field("3m")
    target_return_pct: float | None = Field(
        None, description="Desired expected return (%) over the holding period. Omit for the lowest-risk allocation."
    )


@router.post("/optimize")
async def optimize(req: PortfolioRequest):
    base = req.base.upper()
    targets = sorted({t.upper() for t in req.targets if t.upper() != base})
    if len(targets) < 2:
        raise HTTPException(400, "Select at least two distinct target currencies to build a portfolio")

    horizon_days = period_to_days(req.holding_period)
    lookback = lookback_days_for(horizon_days)
    end = date.today()
    start = end - timedelta(days=lookback)

    series_results = await asyncio.gather(*[data_service.get_series(base, t, start, end) for t in targets])

    returns_by_code: dict[str, pd.Series] = {}
    excluded: list[str] = []
    providers: dict[str, str] = {}
    for code, result in zip(targets, series_results):
        if len(result.observations) < 30:
            excluded.append(code)
            continue
        idx = [d for d, _ in result.observations]
        vals = [r for _, r in result.observations]
        s = pd.Series(vals, index=pd.DatetimeIndex(idx)).sort_index()
        s = s[~s.index.duplicated(keep="last")]
        returns_by_code[code] = log_returns(s).dropna()
        providers[code] = result.provider

    if len(returns_by_code) < 2:
        raise HTTPException(
            502,
            f"Not enough historical data to build a portfolio. Usable: {list(returns_by_code)}, "
            f"excluded for insufficient history: {excluded}",
        )

    try:
        result = port.build_portfolio(
            returns_by_code,
            amount=req.amount,
            fee_pct=req.fee_pct,
            horizon_days=horizon_days,
            target_return_pct=req.target_return_pct,
        )
    except ValueError as exc:
        raise HTTPException(502, str(exc)) from exc

    def meta_for(code: str) -> dict:
        m = get_meta(code)
        return {"code": m.code, "name": m.name, "flag": m.flag}

    return {
        "base": base,
        "holding_period": req.holding_period,
        "horizon_days": result.horizon_days,
        "n_common_days": result.n_common_days,
        "amount": req.amount,
        "fee_pct": req.fee_pct,
        "excluded_codes": excluded,
        "achievable_return_min_pct": safe_float(result.achievable_return_min_pct),
        "achievable_return_max_pct": safe_float(result.achievable_return_max_pct),
        "requested_target_return_pct": safe_float(result.requested_target_return_pct),
        "effective_target_return_pct": safe_float(result.effective_target_return_pct),
        "was_clamped": result.was_clamped,
        "analytic_volatility_pct": safe_float(result.analytic_volatility_pct),
        "risk_level": result.risk_level,
        "allocation": [
            {
                **meta_for(e.code),
                "weight_pct": safe_float(e.weight_pct),
                "amount": safe_float(e.amount),
                "individual_expected_return_pct": safe_float(e.individual_expected_return_pct),
                "individual_volatility_pct": safe_float(e.individual_volatility_pct),
                "provider": providers.get(e.code),
            }
            for e in result.allocation
        ],
        "min_risk_portfolio": {
            "weights_pct": {k: safe_float(v) for k, v in result.min_risk_portfolio.weights.items()},
            "expected_return_pct": safe_float(result.min_risk_portfolio.expected_return_pct),
            "volatility_pct": safe_float(result.min_risk_portfolio.volatility_pct),
        },
        "max_return_portfolio": {
            "weights_pct": {k: safe_float(v) for k, v in result.max_return_portfolio.weights.items()},
            "expected_return_pct": safe_float(result.max_return_portfolio.expected_return_pct),
            "volatility_pct": safe_float(result.max_return_portfolio.volatility_pct),
        },
        "outcome": {k: safe_float(v) for k, v in asdict(result.outcome).items()},
        "correlation_warnings": result.correlation_warnings,
        "note": result.note,
    }
