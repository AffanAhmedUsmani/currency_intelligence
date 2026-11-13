"""Walk-forward validation of the core "buy the dip" signal against a
naive baseline, to check — rather than assume — whether this kind of
signal has had any historical value for a given pair.

Scope decision, documented rather than hidden: a full walk-forward backtest
that recomputes the entire opportunity-scoring pipeline (including a fresh
bootstrap simulation) at every historical date would be computationally
heavy for an interactive API. Instead this module backtests the single
most heavily-weighted, cheapest-to-vectorize signal — the rolling z-score
("currency is statistically cheap vs. its own recent history") — which is
inherently causal (every z-score value only uses data up to and including
that day) so there is no look-ahead bias in signal generation. The forward
return used to *evaluate* each signal correctly looks into the future,
since that's what a backtest is for.

This does not backtest the full weighted opportunity score end-to-end; it
validates the single largest component of it. That's a real limitation,
stated plainly in the API response and the README, not papered over.

Sign convention, stated explicitly because it is easy to get backwards (an
earlier version of this module did): the series is the app's base->quote
RATE (quote units per 1 base unit). A currency is "statistically cheap"
when the RATE is currently ELEVATED versus its own history — a POSITIVE
z-score, not negative — because that means 1 base-currency unit currently
buys MORE of the quote currency than usual. The forward outcome used to
evaluate a signal is therefore the HOLDING VALUE return (`now/future - 1`,
positive when the rate falls back afterward and the quote currency
appreciates), not the rate's own raw forward change. See
`scoring.py`'s `score_valuation_deviation` docstring for the full
derivation — the same direction question, derived and tested independently
there and in `weekly_rotation_backtest.py`.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from app.analytics.meanreversion import rolling_zscore
from app.analytics.scoring import score_valuation_deviation


@dataclass
class BacktestResult:
    horizon_days: int
    z_window: int
    entry_threshold: float
    n_signals: int
    n_baseline_days: int
    signal_hit_rate_pct: float | None
    baseline_hit_rate_pct: float | None
    avg_signal_return_pct: float | None
    avg_baseline_return_pct: float | None
    max_adverse_move_pct: float | None
    brier_score: float | None
    beats_baseline: bool | None
    note: str


def run_backtest(
    series: pd.Series,
    horizon_days: int = 20,
    z_window: int = 30,
    entry_threshold: float = 1.0,
) -> BacktestResult:
    series = series.dropna()
    z = rolling_zscore(series, z_window)
    # Value return from buying at the current rate and converting back at the
    # future rate: positive when the rate falls (quote currency appreciates).
    forward_return_pct = (series / series.shift(-horizon_days) - 1.0) * 100.0

    frame = pd.DataFrame({"z": z, "fwd": forward_return_pct}).dropna()

    if len(frame) < 30:
        return BacktestResult(
            horizon_days=horizon_days,
            z_window=z_window,
            entry_threshold=entry_threshold,
            n_signals=0,
            n_baseline_days=len(frame),
            signal_hit_rate_pct=None,
            baseline_hit_rate_pct=None,
            avg_signal_return_pct=None,
            avg_baseline_return_pct=None,
            max_adverse_move_pct=None,
            brier_score=None,
            beats_baseline=None,
            note="Not enough historical data for a meaningful backtest over this horizon.",
        )

    signal_mask = frame["z"] > entry_threshold
    signal_days = frame[signal_mask]
    baseline_days = frame

    predicted_prob = frame["z"].apply(lambda z_val: score_valuation_deviation(z_val) / 100.0)
    outcome = (frame["fwd"] > 0).astype(float)
    brier = float(((predicted_prob - outcome) ** 2).mean())

    signal_hit_rate = float((signal_days["fwd"] > 0).mean() * 100.0) if len(signal_days) else None
    baseline_hit_rate = float((baseline_days["fwd"] > 0).mean() * 100.0)
    avg_signal_return = float(signal_days["fwd"].mean()) if len(signal_days) else None
    avg_baseline_return = float(baseline_days["fwd"].mean())
    max_adverse = float(signal_days["fwd"].min()) if len(signal_days) else None

    beats_baseline = (
        avg_signal_return is not None and avg_signal_return > avg_baseline_return
        and signal_hit_rate is not None and signal_hit_rate > baseline_hit_rate
    )

    if len(signal_days) < 5:
        note = (
            "Too few historical 'statistically cheap' signals occurred for this pair/window to "
            "draw a reliable conclusion — treat the comparison as indicative only."
        )
    elif beats_baseline:
        note = (
            "Over this history, buying when the z-score signal triggered outperformed the "
            "unconditional baseline on both hit rate and average return — modest support for "
            "this signal on this pair, not a guarantee it continues."
        )
    else:
        note = (
            "Over this history, this signal did NOT clearly outperform simply holding/buying "
            "unconditionally. Treat opportunity scores for this pair with added skepticism."
        )

    return BacktestResult(
        horizon_days=horizon_days,
        z_window=z_window,
        entry_threshold=entry_threshold,
        n_signals=int(len(signal_days)),
        n_baseline_days=int(len(baseline_days)),
        signal_hit_rate_pct=signal_hit_rate,
        baseline_hit_rate_pct=baseline_hit_rate,
        avg_signal_return_pct=avg_signal_return,
        avg_baseline_return_pct=avg_baseline_return,
        max_adverse_move_pct=max_adverse,
        brier_score=brier,
        beats_baseline=beats_baseline,
        note=note,
    )
