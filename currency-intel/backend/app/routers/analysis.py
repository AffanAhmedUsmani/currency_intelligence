from dataclasses import asdict

from fastapi import APIRouter, HTTPException, Query

from app.analytics.backtest import run_backtest
from app.analytics.volatility import log_returns
from app.serializers import safe_float, series_to_points
from app.services.analysis_engine import analyze_pair
from app.services.currency_universe import get_meta

router = APIRouter(prefix="/api/analysis", tags=["analysis"])


def _serialize(analysis) -> dict:
    meta = get_meta(analysis.code)
    opp = analysis.opportunity
    mr = analysis.mean_reversion
    trend = analysis.trend
    forecast = analysis.forecast

    backtest = None
    if len(analysis.series_full.dropna()) >= 60:
        bt = run_backtest(analysis.series_full)
        backtest = {
            "horizon_days": bt.horizon_days,
            "z_window": bt.z_window,
            "entry_threshold": bt.entry_threshold,
            "n_signals": bt.n_signals,
            "n_baseline_days": bt.n_baseline_days,
            "signal_hit_rate_pct": safe_float(bt.signal_hit_rate_pct),
            "baseline_hit_rate_pct": safe_float(bt.baseline_hit_rate_pct),
            "avg_signal_return_pct": safe_float(bt.avg_signal_return_pct),
            "avg_baseline_return_pct": safe_float(bt.avg_baseline_return_pct),
            "max_adverse_move_pct": safe_float(bt.max_adverse_move_pct),
            "brier_score": safe_float(bt.brier_score),
            "beats_baseline": bt.beats_baseline,
            "note": bt.note,
        }

    return {
        "code": analysis.code,
        "base": analysis.base,
        "name": meta.name,
        "flag": meta.flag,
        "latest_rate": safe_float(analysis.latest_rate),
        "pct_change": safe_float(analysis.pct_change),
        "abs_change": safe_float(analysis.abs_change),
        "provider": analysis.provider,
        "rate_kind": analysis.rate_kind,
        "data_warning": analysis.data_error,
        "n_observations": int(len(analysis.series_full.dropna())),
        "chart": {
            "display": series_to_points(analysis.series_display),
            "full_history": series_to_points(analysis.series_full),
        },
        "indicators": {
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
            "note": "ATR and the stochastic oscillator are close-price proxies here (no intraday high/low data is available from either provider), not canonical OHLC indicators.",
        },
        "volatility": {
            "annualized": series_to_points(analysis.volatility_annualized),
            "ewma_annualized": series_to_points(analysis.ewma_volatility),
            "percentile": safe_float(analysis.vol_percentile),
            "regime": analysis.vol_regime,
            "max_drawdown_pct": safe_float(analysis.max_drawdown_pct),
            "downside_deviation_pct": safe_float(analysis.downside_deviation_pct),
        },
        "mean_reversion": {
            "zscore": safe_float(mr.zscore) if mr else None,
            "bollinger_position": safe_float(mr.bollinger_position) if mr else None,
            "ar1_coefficient": safe_float(mr.ar1_coefficient) if mr else None,
            "half_life_days": safe_float(mr.half_life_days) if mr else None,
            "is_statistically_supported": mr.is_statistically_supported if mr else False,
            "note": mr.note if mr else "",
        },
        "trend": {
            "direction": trend.direction if trend else "unknown",
            "momentum_state": trend.momentum_state if trend else "unknown",
            "reversal_signal": trend.reversal_signal if trend else None,
            "short_vs_long_pct": safe_float(trend.short_vs_long_pct) if trend else None,
        },
        "forecast": {
            "horizon_days": forecast.horizon_days if forecast else None,
            "expected_pct_move": safe_float(forecast.expected_pct_move) if forecast else None,
            "prob_appreciation": safe_float(forecast.prob_appreciation) if forecast else None,
            "prob_depreciation": safe_float(forecast.prob_depreciation) if forecast else None,
            "ci_low_pct": safe_float(forecast.ci_low_pct) if forecast else None,
            "ci_high_pct": safe_float(forecast.ci_high_pct) if forecast else None,
            "secondary_trend_pct": safe_float(forecast.secondary_trend_pct) if forecast else None,
            "method": forecast.method if forecast else None,
            "confidence": forecast.confidence if forecast else "insufficient_data",
            "note": forecast.note if forecast else "",
        },
        "support_estimate": safe_float(analysis.support_estimate),
        "resistance_estimate": safe_float(analysis.resistance_estimate),
        "opportunity": {
            "score": safe_float(opp.score) if opp else None,
            "classification": opp.classification if opp else "WAIT / MONITOR",
            "components": {k: safe_float(v) for k, v in asdict(opp.components).items()} if opp else {},
            "supporting_signals": opp.supporting_signals if opp else [],
            "contradicting_signals": opp.contradicting_signals if opp else [],
            "risks": opp.risks if opp else [],
            "invalidation_conditions": opp.invalidation_conditions if opp else [],
            "summary": opp.summary if opp else "",
        },
        "backtest": backtest,
    }


@router.get("/{base}/{target}")
async def get_analysis(base: str, target: str, period: str = Query("1m")):
    analysis = await analyze_pair(base.upper(), target.upper(), period)
    if analysis.data_error and analysis.series_full.empty:
        raise HTTPException(502, analysis.data_error)
    return _serialize(analysis)
