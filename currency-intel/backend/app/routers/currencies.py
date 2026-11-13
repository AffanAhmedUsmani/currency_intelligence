from fastapi import APIRouter

from app.services.currency_universe import CURRENCIES, DEFAULT_MAJORS

router = APIRouter(prefix="/api/currencies", tags=["currencies"])


@router.get("")
def list_currencies():
    return {
        "currencies": [
            {"code": m.code, "name": m.name, "flag": m.flag, "liquidity_tier": m.liquidity_tier}
            for m in CURRENCIES.values()
        ],
        "default_majors": DEFAULT_MAJORS,
    }
