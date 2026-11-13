from datetime import datetime

from fastapi import APIRouter

from app.providers.frankfurter import FrankfurterProvider
from app.providers.yahoo import YahooFinanceProvider
from app.services import data_service

router = APIRouter(prefix="/api/health", tags=["health"])


@router.get("")
async def health():
    results = {}
    for provider in (FrankfurterProvider(), YahooFinanceProvider()):
        try:
            data = await provider.get_latest("USD", ["EUR"])
            results[provider.name] = "ok" if data else "no_data"
        except Exception as exc:  # noqa: BLE001
            results[provider.name] = f"error: {exc}"

    return {
        "status": "ok",
        "time": datetime.utcnow().isoformat() + "Z",
        "providers": results,
        "database": "sqlite",
    }
