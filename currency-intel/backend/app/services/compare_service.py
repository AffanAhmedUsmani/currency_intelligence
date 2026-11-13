"""Shared logic for building currency comparison cards, used by both the
/api/compare and /api/opportunities routers so "top buying opportunities"
and "the full comparison grid" are always derived from the same analysis,
never two diverging code paths.
"""

import asyncio

from app.serializers import safe_float, series_to_points
from app.services.analysis_engine import analyze_pair
from app.services.currency_universe import DEFAULT_MAJORS, all_codes, get_meta

_CONCURRENCY_LIMIT = 8


async def build_cards(base: str, period: str, candidates: list[str]) -> list[dict]:
    base = base.upper()
    candidates = [c.upper() for c in candidates if c.upper() != base]
    sem = asyncio.Semaphore(_CONCURRENCY_LIMIT)

    async def bounded(code: str):
        async with sem:
            try:
                return code, await analyze_pair(base, code, period)
            except Exception as exc:  # noqa: BLE001 - surface as a per-card error, don't fail the batch
                return code, exc

    results = await asyncio.gather(*[bounded(c) for c in candidates])

    cards = []
    for code, analysis in results:
        if isinstance(analysis, Exception):
            continue
        if analysis.data_error and analysis.series_full.empty:
            continue

        meta = get_meta(code)
        opp = analysis.opportunity
        trend = analysis.trend
        sparkline = analysis.series_display.tail(90)

        cards.append(
            {
                "code": code,
                "name": meta.name,
                "flag": meta.flag,
                "current_rate": safe_float(analysis.latest_rate),
                "pct_change": safe_float(analysis.pct_change),
                "abs_change": safe_float(analysis.abs_change),
                "sparkline": [safe_float(v) for v in sparkline.values],
                "volatility_classification": analysis.vol_regime,
                "volatility_percentile": safe_float(analysis.vol_percentile),
                "momentum_classification": trend.momentum_state if trend else "unknown",
                "trend_direction": trend.direction if trend else "unknown",
                "reversal_signal": trend.reversal_signal if trend else None,
                "opportunity_score": safe_float(opp.score) if opp else None,
                "recommendation": opp.classification if opp else "WAIT / MONITOR",
                "recommendation_summary": opp.summary if opp else "",
                "provider": analysis.provider,
                "rate_kind": analysis.rate_kind,
                "data_warning": analysis.data_error,
            }
        )
    return cards


def resolve_candidates(universe: str, base: str) -> list[str]:
    base = base.upper()
    all_c = [c for c in all_codes() if c != base]
    majors = [c for c in DEFAULT_MAJORS if c != base]
    if universe == "majors":
        return majors
    return all_c


def rank_for_universe(cards: list[dict], universe: str, limit: int) -> list[dict]:
    if universe == "volatile":
        ranked = sorted(cards, key=lambda c: c["volatility_percentile"] or -1, reverse=True)
    elif universe == "strongest":
        ranked = sorted(cards, key=lambda c: c["pct_change"] or float("-inf"), reverse=True)
    elif universe == "weakest":
        ranked = sorted(cards, key=lambda c: c["pct_change"] or float("inf"))
    else:
        ranked = sorted(cards, key=lambda c: c["opportunity_score"] or 0, reverse=True)
    return ranked[:limit] if limit else ranked


_MOMENTUM_RANK = {
    "accelerating_up": 5, "decelerating_up": 4, "flat": 3,
    "decelerating_down": 2, "accelerating_down": 1, "unknown": 0,
}


def market_summary(cards: list[dict]) -> dict:
    if not cards:
        return {}

    def best(key, reverse=False, filter_fn=None):
        pool = [c for c in cards if filter_fn(c)] if filter_fn else cards
        pool = [c for c in pool if c.get(key) is not None]
        if not pool:
            return None
        return max(pool, key=lambda c: c[key]) if reverse else min(pool, key=lambda c: c[key])

    best_opportunity = max(cards, key=lambda c: c["opportunity_score"] or 0)
    strongest_performer = best("pct_change", reverse=True)
    biggest_decline = best("pct_change", reverse=False)
    highest_volatility = best("volatility_percentile", reverse=True)
    most_stable = best("volatility_percentile", reverse=False)
    strongest_momentum = max(cards, key=lambda c: _MOMENTUM_RANK.get(c["momentum_classification"], 0))
    reversal_candidates = [c for c in cards if c.get("reversal_signal") == "bullish_crossover"]
    possible_reversal = (
        max(reversal_candidates, key=lambda c: c["opportunity_score"] or 0) if reversal_candidates else None
    )

    def pick(card):
        return None if card is None else {"code": card["code"], "name": card["name"], "flag": card["flag"]}

    return {
        "best_buying_opportunity": pick(best_opportunity),
        "strongest_performer": pick(strongest_performer),
        "biggest_decline": pick(biggest_decline),
        "highest_volatility": pick(highest_volatility),
        "most_stable": pick(most_stable),
        "strongest_momentum": pick(strongest_momentum),
        "possible_trend_reversal": pick(possible_reversal),
    }
