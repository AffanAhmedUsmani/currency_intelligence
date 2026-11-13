from fastapi import APIRouter, HTTPException, Query

from app.serializers import series_to_points
from app.services.analysis_engine import analyze_pair

router = APIRouter(prefix="/api/indicators", tags=["indicators"])


@router.get("/{base}/{target}")
async def get_indicators(base: str, target: str, period: str = Query("1m")):
    analysis = await analyze_pair(base.upper(), target.upper(), period)
    if analysis.data_error and analysis.series_full.empty:
        raise HTTPException(502, analysis.data_error)
    return {
        "base": base.upper(),
        "target": target.upper(),
        "sma": {str(w): series_to_points(s) for w, s in analysis.sma.items()},
        "ema20": series_to_points(analysis.ema20),
        "rsi14": series_to_points(analysis.rsi),
        "macd": {
            "line": series_to_points(analysis.macd_line),
            "signal": series_to_points(analysis.macd_signal),
            "histogram": series_to_points(analysis.macd_hist),
        },
        "bollinger": {
            "mid": series_to_points(analysis.bollinger_mid),
            "upper": series_to_points(analysis.bollinger_upper),
            "lower": series_to_points(analysis.bollinger_lower),
        },
        "roc": series_to_points(analysis.roc),
        "momentum": series_to_points(analysis.momentum),
        "atr_proxy": series_to_points(analysis.atr_proxy),
        "stochastic_proxy": series_to_points(analysis.stochastic_proxy),
        "note": "ATR and the stochastic oscillator are close-price proxies (no intraday OHLC data available).",
    }
