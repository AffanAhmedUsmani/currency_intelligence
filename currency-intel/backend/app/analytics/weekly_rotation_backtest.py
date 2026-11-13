"""Walk-forward backtest of the exact strategy this app's basket feature is
built to support: every `rebalance_days`, rotate into whichever `top_n`
candidate currencies currently look statistically cheapest, hold them, then
rotate again — not the single-pair signal test in `backtest.py`.

Methodology, and why it avoids look-ahead bias:

  - At every rebalance checkpoint t, each candidate's rolling z-score
    (`meanreversion.rolling_zscore`, already causal — a value at t only
    uses data up to and including t) is read as of t. Nothing after t is
    used to make the pick.
  - The top-N currencies with the most POSITIVE z-score are selected and
    EQUAL-weighted — not mean-variance optimized like the live basket, on
    purpose: equal weighting isolates "does the *selection* add value" from
    "does the optimizer add value", and avoids adding another source of
    in-sample fitting to what's supposed to be an honest out-of-sample test.
    Positive, not negative: the series is the app's base->quote RATE, where
    a currently-elevated rate (positive z-score) means the quote currency
    is currently CHEAP relative to its own history (1 base-currency unit
    buys more of it than usual) — the buy-favorable direction. This exact
    sign question is also derived and tested in `scoring.py`
    (`score_valuation_deviation`'s docstring) and was caught here first: an
    earlier version of this module picked the most-negative z-score and its
    own synthetic-data test failed, which is what surfaced the same
    pre-existing bug in the live scoring engine.
  - The realized return from t to t+rebalance_days is then measured (this
    step correctly looks at "future" data relative to t — that's what a
    backtest evaluates, not what it uses to decide).
  - Compared against the honest benchmark of equal-weighting ALL candidates
    every period — this tests whether picking the top-N by z-score beats
    simply diversifying across the whole universe, i.e. whether the
    selection signal has any real discriminating power.

Stated scope decision: this validates the single heaviest-weighted signal
behind currency selection (the valuation z-score) with equal weighting, not
the full live opportunity score (which also folds in trend/momentum/
forecast components) or the live mean-variance-optimized allocation.
Re-running the full scoring engine and a bootstrap forecast for every
candidate at every historical weekly checkpoint would be far too slow for
an interactive endpoint — the same trade-off `backtest.py` already makes
for a single pair, extended here to cross-sectional selection.
"""

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from app.analytics.meanreversion import rolling_zscore

MIN_CHECKPOINTS = 8


@dataclass
class RotationPeriod:
    date: str
    selected: list[str]
    strategy_return_pct: float
    benchmark_return_pct: float


@dataclass
class WeeklyRotationResult:
    n_candidates: int
    n_checkpoints: int
    rebalance_days: int
    top_n: int
    zscore_window: int
    strategy_cumulative_return_pct: float
    benchmark_cumulative_return_pct: float
    strategy_annualized_return_pct: float | None
    benchmark_annualized_return_pct: float | None
    strategy_win_rate_pct: float
    benchmark_win_rate_pct: float
    strategy_avg_period_return_pct: float
    strategy_period_return_std_pct: float
    strategy_sharpe_like: float | None
    strategy_max_drawdown_pct: float
    beats_benchmark: bool
    selection_frequency: dict[str, int] = field(default_factory=dict)
    periods: list[RotationPeriod] = field(default_factory=list)
    note: str = ""


def _max_drawdown_from_period_returns(returns_pct: list[float]) -> float:
    if not returns_pct:
        return 0.0
    equity = np.cumprod([1.0 + r / 100.0 for r in returns_pct])
    running_max = np.maximum.accumulate(equity)
    drawdown = (equity - running_max) / running_max
    return float(drawdown.min() * 100.0)


def _insufficient_result(n_candidates: int, n_checkpoints: int, rebalance_days: int, top_n: int, zscore_window: int) -> WeeklyRotationResult:
    return WeeklyRotationResult(
        n_candidates=n_candidates, n_checkpoints=n_checkpoints, rebalance_days=rebalance_days,
        top_n=top_n, zscore_window=zscore_window, strategy_cumulative_return_pct=0.0,
        benchmark_cumulative_return_pct=0.0, strategy_annualized_return_pct=None,
        benchmark_annualized_return_pct=None, strategy_win_rate_pct=0.0, benchmark_win_rate_pct=0.0,
        strategy_avg_period_return_pct=0.0, strategy_period_return_std_pct=0.0,
        strategy_sharpe_like=None, strategy_max_drawdown_pct=0.0, beats_benchmark=False,
        selection_frequency={}, periods=[],
        note=(
            f"Not enough historical data for a meaningful walk-forward test (found {n_checkpoints} "
            f"rebalance periods among {n_candidates} candidates, need at least {MIN_CHECKPOINTS})."
        ),
    )


def backtest_weekly_rotation(
    price_series_by_code: dict[str, pd.Series],
    top_n: int = 3,
    rebalance_days: int = 7,
    zscore_window: int = 30,
    fee_pct: float = 0.0,
) -> WeeklyRotationResult:
    """`price_series_by_code` holds each candidate's base->quote RATE series
    (same convention as the rest of the app), date-indexed, ideally all
    sharing the same long (~2 year) history already fetched elsewhere.
    """
    df = pd.DataFrame(price_series_by_code).sort_index()
    codes = list(df.columns)
    n = len(df)

    if n < zscore_window + rebalance_days * MIN_CHECKPOINTS or len(codes) < top_n:
        return _insufficient_result(len(codes), 0, rebalance_days, top_n, zscore_window)

    zscores = pd.DataFrame({c: rolling_zscore(df[c], zscore_window) for c in codes})

    checkpoints = list(range(zscore_window, n - rebalance_days, rebalance_days))
    if len(checkpoints) < MIN_CHECKPOINTS:
        return _insufficient_result(len(codes), len(checkpoints), rebalance_days, top_n, zscore_window)

    fee_mult_sq = (1.0 - fee_pct / 100.0) ** 2
    selection_counts: dict[str, int] = {c: 0 for c in codes}
    periods: list[RotationPeriod] = []

    for t in checkpoints:
        row_z = zscores.iloc[t]
        row_now = df.iloc[t]
        row_future = df.iloc[t + rebalance_days]

        valid_mask = row_z.notna() & row_now.notna() & row_future.notna()
        valid_codes = [c for c in codes if bool(valid_mask[c])]
        if len(valid_codes) < top_n:
            continue

        ranked = sorted(valid_codes, key=lambda c: row_z[c], reverse=True)  # most positive (cheapest) first
        selected = ranked[:top_n]

        def value_return_pct(code: str) -> float:
            return (row_now[code] / row_future[code] - 1.0) * 100.0

        strat_raw = float(np.mean([value_return_pct(c) for c in selected]))
        strat_period_return = ((1.0 + strat_raw / 100.0) * fee_mult_sq - 1.0) * 100.0

        bench_raw = float(np.mean([value_return_pct(c) for c in valid_codes]))
        bench_period_return = ((1.0 + bench_raw / 100.0) * fee_mult_sq - 1.0) * 100.0

        for c in selected:
            selection_counts[c] += 1

        idx = df.index[t]
        periods.append(
            RotationPeriod(
                date=idx.date().isoformat() if hasattr(idx, "date") else str(idx),
                selected=selected,
                strategy_return_pct=strat_period_return,
                benchmark_return_pct=bench_period_return,
            )
        )

    if len(periods) < MIN_CHECKPOINTS:
        return _insufficient_result(len(codes), len(periods), rebalance_days, top_n, zscore_window)

    strat_returns = [p.strategy_return_pct for p in periods]
    bench_returns = [p.benchmark_return_pct for p in periods]
    n_periods = len(periods)

    strat_cumulative = float((np.prod([1.0 + r / 100.0 for r in strat_returns]) - 1.0) * 100.0)
    bench_cumulative = float((np.prod([1.0 + r / 100.0 for r in bench_returns]) - 1.0) * 100.0)

    periods_per_year = 365.0 / rebalance_days
    years = n_periods / periods_per_year
    strat_annualized = (
        float(((1.0 + strat_cumulative / 100.0) ** (1.0 / years) - 1.0) * 100.0) if years > 0 else None
    )
    bench_annualized = (
        float(((1.0 + bench_cumulative / 100.0) ** (1.0 / years) - 1.0) * 100.0) if years > 0 else None
    )

    strat_win_rate = float(np.mean([r > 0 for r in strat_returns]) * 100.0)
    bench_win_rate = float(np.mean([r > 0 for r in bench_returns]) * 100.0)
    strat_avg = float(np.mean(strat_returns))
    strat_std = float(np.std(strat_returns, ddof=1)) if n_periods > 1 else 0.0
    sharpe_like = (strat_avg / strat_std * np.sqrt(periods_per_year)) if strat_std > 0 else None
    max_dd = _max_drawdown_from_period_returns(strat_returns)
    beats_benchmark = strat_cumulative > bench_cumulative

    if n_periods < 20:
        note = (
            f"Only {n_periods} historical rotation periods were available — treat this as indicative, "
            "not conclusive. More history (or a shorter rebalance interval) would make this more reliable."
        )
    elif beats_benchmark:
        note = (
            f"Over {n_periods} historical {rebalance_days}-day periods, rotating into the top-{top_n} "
            f"statistically cheapest currencies outperformed equally diversifying across all "
            f"{len(codes)} candidates every period — modest support for this selection approach on this "
            "base currency and universe, not a guarantee it continues."
        )
    else:
        note = (
            f"Over {n_periods} historical {rebalance_days}-day periods, this selection approach did NOT "
            f"clearly outperform simply diversifying across all {len(codes)} candidates every period. "
            "Treat the live picks for this base currency with added skepticism."
        )

    return WeeklyRotationResult(
        n_candidates=len(codes), n_checkpoints=n_periods, rebalance_days=rebalance_days, top_n=top_n,
        zscore_window=zscore_window, strategy_cumulative_return_pct=strat_cumulative,
        benchmark_cumulative_return_pct=bench_cumulative, strategy_annualized_return_pct=strat_annualized,
        benchmark_annualized_return_pct=bench_annualized, strategy_win_rate_pct=strat_win_rate,
        benchmark_win_rate_pct=bench_win_rate, strategy_avg_period_return_pct=strat_avg,
        strategy_period_return_std_pct=strat_std, strategy_sharpe_like=sharpe_like,
        strategy_max_drawdown_pct=max_dd, beats_benchmark=beats_benchmark,
        selection_frequency={c: v for c, v in selection_counts.items() if v > 0},
        periods=periods, note=note,
    )
