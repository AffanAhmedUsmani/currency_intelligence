from datetime import datetime

from fastapi import APIRouter, HTTPException, Query

from app.services.compare_service import build_cards, market_summary, rank_for_universe, resolve_candidates

router = APIRouter(prefix="/api/compare", tags=["compare"])

VALID_UNIVERSES = {"majors", "volatile", "strongest", "weakest", "all"}


@router.get("")
async def compare(
    base: str = Query("PKR"),
    period: str = Query("1m"),
    universe: str = Query("majors"),
    limit: int = Query(20, ge=1, le=100),
):
    base = base.upper()
    if universe not in VALID_UNIVERSES:
        raise HTTPException(400, f"universe must be one of {sorted(VALID_UNIVERSES)}")

    candidates = resolve_candidates(universe, base)
    if not candidates:
        raise HTTPException(400, "No comparison currencies available for this base currency")

    all_cards = await build_cards(base, period, candidates)
    if not all_cards:
        raise HTTPException(502, "Could not retrieve data for any currency in this universe right now")

    effective_limit = limit if universe != "all" else min(limit, len(all_cards))
    cards = rank_for_universe(all_cards, universe, effective_limit)

    return {
        "base": base,
        "period": period,
        "universe": universe,
        "last_updated": datetime.utcnow().isoformat() + "Z",
        "count": len(cards),
        "summary": market_summary(cards),
        "cards": cards,
    }
