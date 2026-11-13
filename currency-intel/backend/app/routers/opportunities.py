from fastapi import APIRouter, Query

from app.services.compare_service import build_cards, resolve_candidates

router = APIRouter(prefix="/api/opportunities", tags=["opportunities"])


@router.get("")
async def opportunities(
    base: str = Query("PKR"),
    period: str = Query("1m"),
    top_n: int = Query(5, ge=1, le=20),
    universe: str = Query("all"),
):
    base = base.upper()
    candidates = resolve_candidates(universe, base)
    cards = await build_cards(base, period, candidates)
    ranked = sorted(cards, key=lambda c: c["opportunity_score"] or 0, reverse=True)
    return {
        "base": base,
        "period": period,
        "top_opportunities": ranked[:top_n],
    }
