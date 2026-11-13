"""Ties the data layer and analytics modules together into one bundle per
currency pair, reused by every API router so /compare, /opportunities,
/analysis and /indicators all compute from the exact same logic.
"""

from dataclasses import dataclass, field
from datetime import date, timedelta

import numpy as np
import pandas as pd

from app.analytics import indicators as ind
from app.analytics import volatility as vol
from app.analytics import meanreversion as mr
from app.analytics import trend as trd
from app.analytics import forecast as fc
from app.analytics import scoring as sc
from app.services import data_service

PERIOD_DAYS = {
    "24h": 1,
    "7d": 7,
    "14d": 14,
    "1m": 30,
    "3m": 90,
    "6m": 182,
    "1y": 365,
    "2y": 730,
    "5y": 1825,
}

MIN_OBS_FOR_CONFIDENCE = 30


def period_to_days(period: str) -> int:
    return PERIOD_DAYS.get(period, 30)


ANALYTICAL_LOOKBACK_DAYS = 730  # ~2 years — the statistical reference window for every calculation


def lookback_days_for(period_days: int) -> int:
    """The historical window actually fetched and fed into every indicator,
    volatility, mean-reversion, forecast, and backtest calculation.

    This is deliberately decoupled from `period_days` (the user's selected
    display/holding window) and pinned to a fixed ~2-year reference window
    instead. A z-score, a volatility percentile, an AR(1) mean-reversion
    fit, a bootstrap forecast, and a backtest's signal count are all more
    statistically sound when computed against a long, consistent history —
    if the lookback shrank to match a 1-month display window, there often
    wouldn't be enough data for a 200-day moving average, a meaningful
    volatility percentile, or more than a handful of backtest signals.
    `period_days` still controls what's *displayed* (the chart slice, the
    pct-change headline, the forecast horizon) — it just no longer controls
    how much history the underlying statistics are computed from.
    """
    return max(period_days + 30, ANALYTICAL_LOOKBACK_DAYS)


@dataclass
class CurrencyAnalysis:
    code: str
    base: str
    series_full: pd.Series
    series_display: pd.Series
    latest_rate: float
    pct_change: float | None
    abs_change: float | None
    provider: str
    rate_kind: str
    data_error: str | None

    sma: dict[int, pd.Series] = field(default_factory=dict)
    ema20: pd.Series | None = None
    rsi: pd.Series | None = None
    macd_line: pd.Series | None = None
    macd_signal: pd.Series | None = None
    macd_hist: pd.Series | None = None
    bollinger_mid: pd.Series | None = None
    bollinger_upper: pd.Series | None = None
    bollinger_lower: pd.Series | None = None
    roc: pd.Series | None = None
    momentum: pd.Series | None = None
    atr_proxy: pd.Series | None = None
    stochastic_proxy: pd.Series | None = None

    volatility_annualized: pd.Series | None = None
    ewma_volatility: pd.Series | None = None
    vol_percentile: float | None = None
    vol_regime: str = "unknown"
    max_drawdown_pct: float | None = None
    downside_deviation_pct: float | None = None

    mean_reversion: mr.MeanReversionResult | None = None
    trend: trd.TrendResult | None = None
    forecast: fc.ForecastResult | None = None
    opportunity: sc.OpportunityResult | None = None

    support_estimate: float | None = None
    resistance_estimate: float | None = None


def _support_resistance(series: pd.Series, window: int = 30) -> tuple[float | None, float | None]:
    recent = series.tail(window)
    if recent.empty:
        return None, None
    return float(recent.min()), float(recent.max())


async def analyze_pair(base: str, quote: str, period: str) -> CurrencyAnalysis:
    period_days = period_to_days(period)
    lookback = lookback_days_for(period_days)
    end = date.today()
    start = end - timedelta(days=lookback)

    series_result = await data_service.get_series(base, quote, start, end)

    if not series_result.observations:
        empty = pd.Series(dtype=float)
        return CurrencyAnalysis(
            code=quote, base=base, series_full=empty, series_display=empty,
            latest_rate=float("nan"), pct_change=None, abs_change=None,
            provider=series_result.provider, rate_kind=series_result.rate_kind,
            data_error=series_result.error or "No data available for this pair.",
        )

    idx = [d for d, _ in series_result.observations]
    vals = [r for _, r in series_result.observations]
    series_full = pd.Series(vals, index=pd.DatetimeIndex(idx)).sort_index()
    series_full = series_full[~series_full.index.duplicated(keep="last")]

    display_start = end - timedelta(days=period_days)
    series_display = series_full[series_full.index.date >= display_start]
    if series_display.empty:
        series_display = series_full.tail(max(2, min(len(series_full), period_days)))

    latest_rate = float(series_full.iloc[-1])
    first_display = float(series_display.iloc[0]) if len(series_display) else latest_rate
    pct_change = ((latest_rate / first_display) - 1.0) * 100.0 if first_display else None
    abs_change = latest_rate - first_display

    analysis = CurrencyAnalysis(
        code=quote, base=base, series_full=series_full, series_display=series_display,
        latest_rate=latest_rate, pct_change=pct_change, abs_change=abs_change,
        provider=series_result.provider, rate_kind=series_result.rate_kind,
        data_error=series_result.error,
    )

    for window in (7, 14, 30, 50, 200):
        if len(series_full) >= window:
            analysis.sma[window] = ind.sma(series_full, window)

    analysis.ema20 = ind.ema(series_full, 20) if len(series_full) >= 20 else None
    analysis.rsi = ind.rsi(series_full, 14) if len(series_full) >= 15 else None
    if len(series_full) >= 35:
        analysis.macd_line, analysis.macd_signal, analysis.macd_hist = ind.macd(series_full)
    if len(series_full) >= 20:
        analysis.bollinger_mid, analysis.bollinger_upper, analysis.bollinger_lower = ind.bollinger_bands(series_full)
    analysis.roc = ind.roc(series_full, min(14, max(2, len(series_full) - 1)))
    analysis.momentum = ind.momentum(series_full, min(10, max(2, len(series_full) - 1)))
    if len(series_full) >= 15:
        analysis.atr_proxy = ind.atr_proxy(series_full)
        analysis.stochastic_proxy = ind.stochastic_proxy(series_full)

    returns = vol.log_returns(series_full)
    vwindow = min(30, max(5, len(series_full) // 2))
    analysis.volatility_annualized = vol.annualized_volatility(returns, vwindow)
    analysis.ewma_volatility = vol.ewma_volatility(returns)
    analysis.vol_percentile = vol.volatility_percentile(analysis.ewma_volatility)
    analysis.vol_regime = vol.volatility_regime(analysis.vol_percentile)
    analysis.max_drawdown_pct = vol.max_drawdown(series_full) if len(series_full) >= 2 else None
    analysis.downside_deviation_pct = vol.downside_deviation(returns) if len(series_full) >= 10 else None

    if analysis.bollinger_mid is not None:
        analysis.mean_reversion = mr.analyze(
            series_full, analysis.bollinger_mid, analysis.bollinger_upper, analysis.bollinger_lower
        )
    else:
        analysis.mean_reversion = mr.MeanReversionResult(
            zscore=None, bollinger_position=None, ar1_coefficient=None, half_life_days=None,
            is_statistically_supported=False, note="Not enough history to assess mean reversion.",
        )

    short_ma = analysis.sma.get(14, analysis.ema20 if analysis.ema20 is not None else series_full)
    long_ma = analysis.sma.get(50, analysis.sma.get(30, series_full))
    analysis.trend = trd.analyze(short_ma, long_ma, analysis.roc)

    analysis.forecast = fc.bootstrap_forecast(returns, horizon_days=min(30, max(5, period_days)))

    rsi_latest = (
        float(analysis.rsi.iloc[-1])
        if analysis.rsi is not None and not analysis.rsi.empty and not np.isnan(analysis.rsi.iloc[-1])
        else None
    )

    analysis.opportunity = sc.compute_opportunity(
        code=quote,
        pct_change=pct_change,
        zscore=analysis.mean_reversion.zscore,
        mean_reversion=analysis.mean_reversion,
        trend=analysis.trend,
        rsi_latest=rsi_latest,
        vol_percentile=analysis.vol_percentile,
        forecast=analysis.forecast,
        n_observations=len(series_full),
        min_observations=MIN_OBS_FOR_CONFIDENCE,
    )

    analysis.support_estimate, analysis.resistance_estimate = _support_resistance(series_full)

    return analysis
