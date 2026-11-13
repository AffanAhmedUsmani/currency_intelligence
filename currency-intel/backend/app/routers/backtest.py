import asyncio
from dataclasses import asdict
from datetime import date, timedelta

import pandas as pd
from fastapi import APIRouter, HTTPException, Query

from app.analytics.weekly_rotation_backtest import backtest_weekly_rotation
from app.serializers import safe_float
from app.services import data_service
from app.services.analysis_engine import ANALYTICAL_LOOKBACK_DAYS
from app.services.compare_service import resolve_candidates
from app.services.currency_universe import get_meta

router = APIRouter(prefix="/api/backtest", tags=["backtest"])


@router.get("/weekly-rotation")
async def weekly_rotation(
    base: str = Query("PKR"),
    universe: str = Query("majors"),
    top_n: int = Query(3, ge=1, le=10),
    rebalance_days: int = Query(7, ge=1, le=90),
    fee_pct: float = Query(1.5, ge=0, le=20),
):
    base = base.upper()
    candidates = resolve_candidates(universe, base)
    if len(candidates) < top_n:
        raise HTTPException(400, f"Universe '{universe}' has too few currencies for top_n={top_n}")

    end = date.today()
    start = end - timedelta(days=ANALYTICAL_LOOKBACK_DAYS + 30)
    results = await asyncio.gather(*[data_service.get_series(base, c, start, end) for c in candidates])

    price_series_by_code: dict[str, pd.Series] = {}
    excluded: list[str] = []
    for code, res in zip(candidates, results):
        if len(res.observations) < 60:
            excluded.append(code)
            continue
        idx = [d for d, _ in res.observations]
        vals = [r for _, r in res.observations]
        s = pd.Series(vals, index=pd.DatetimeIndex(idx)).sort_index()
        s = s[~s.index.duplicated(keep="last")]
        price_series_by_code[code] = s

    if len(price_series_by_code) < top_n:
        raise HTTPException(
            502,
            f"Not enough currencies with sufficient history in universe '{universe}'. "
            f"Usable: {list(price_series_by_code)}, excluded: {excluded}",
        )

    result = backtest_weekly_rotation(
        price_series_by_code, top_n=top_n, rebalance_days=rebalance_days, fee_pct=fee_pct,
    )

    def meta_for(code: str) -> dict:
        m = get_meta(code)
        return {"code": m.code, "name": m.name, "flag": m.flag}

    return {
        "base": base,
        "universe": universe,
        "top_n": result.top_n,
        "rebalance_days": result.rebalance_days,
        "zscore_window": result.zscore_window,
        "fee_pct": fee_pct,
        "n_candidates": result.n_candidates,
        "n_checkpoints": result.n_checkpoints,
        "excluded_codes": excluded,
        "strategy_cumulative_return_pct": safe_float(result.strategy_cumulative_return_pct),
        "benchmark_cumulative_return_pct": safe_float(result.benchmark_cumulative_return_pct),
        "strategy_annualized_return_pct": safe_float(result.strategy_annualized_return_pct),
        "benchmark_annualized_return_pct": safe_float(result.benchmark_annualized_return_pct),
        "strategy_win_rate_pct": safe_float(result.strategy_win_rate_pct),
        "benchmark_win_rate_pct": safe_float(result.benchmark_win_rate_pct),
        "strategy_avg_period_return_pct": safe_float(result.strategy_avg_period_return_pct),
        "strategy_period_return_std_pct": safe_float(result.strategy_period_return_std_pct),
        "strategy_sharpe_like": safe_float(result.strategy_sharpe_like),
        "strategy_max_drawdown_pct": safe_float(result.strategy_max_drawdown_pct),
        "beats_benchmark": result.beats_benchmark,
        "selection_frequency": [
            {**meta_for(code), "times_selected": count, "pct_of_periods": safe_float(count / result.n_checkpoints * 100.0) if result.n_checkpoints else 0.0}
            for code, count in sorted(result.selection_frequency.items(), key=lambda kv: -kv[1])
        ],
        "periods": [
            {
                "date": p.date,
                "selected": p.selected,
                "strategy_return_pct": safe_float(p.strategy_return_pct),
                "benchmark_return_pct": safe_float(p.benchmark_return_pct),
            }
            for p in result.periods
        ],
        "note": result.note,
    }
