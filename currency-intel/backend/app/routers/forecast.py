from fastapi import APIRouter, HTTPException, Query

from app.serializers import safe_float
from app.services.analysis_engine import analyze_pair

router = APIRouter(prefix="/api/forecast", tags=["forecast"])


@router.get("/{base}/{target}")
async def get_forecast(base: str, target: str, period: str = Query("1m")):
    analysis = await analyze_pair(base.upper(), target.upper(), period)
    if analysis.data_error and analysis.series_full.empty:
        raise HTTPException(502, analysis.data_error)
    f = analysis.forecast
    return {
        "base": base.upper(),
        "target": target.upper(),
        "horizon_days": f.horizon_days if f else None,
        "expected_pct_move": safe_float(f.expected_pct_move) if f else None,
        "prob_appreciation": safe_float(f.prob_appreciation) if f else None,
        "prob_depreciation": safe_float(f.prob_depreciation) if f else None,
        "ci_low_pct": safe_float(f.ci_low_pct) if f else None,
        "ci_high_pct": safe_float(f.ci_high_pct) if f else None,
        "secondary_trend_pct": safe_float(f.secondary_trend_pct) if f else None,
        "method": f.method if f else None,
        "confidence": f.confidence if f else "insufficient_data",
        "note": f.note if f else "",
    }
