from datetime import date, datetime, timedelta

from fastapi import APIRouter, HTTPException, Query

from app.serializers import series_to_points
from app.services import data_service
from app.services.analysis_engine import period_to_days

router = APIRouter(prefix="/api/rates", tags=["rates"])


@router.get("/latest")
async def latest(base: str = Query(...), quotes: str = Query(..., description="Comma-separated currency codes")):
    quote_list = [q.strip().upper() for q in quotes.split(",") if q.strip()]
    if not quote_list:
        raise HTTPException(400, "At least one quote currency is required")
    try:
        rates, provider, rate_kind = await data_service.get_latest(base.upper(), quote_list)
    except Exception as exc:
        raise HTTPException(502, f"Could not retrieve latest rates: {exc}") from exc
    return {
        "base": base.upper(),
        "rates": rates,
        "provider": provider,
        "rate_kind": rate_kind,
        "fetched_at": datetime.utcnow().isoformat() + "Z",
    }


@router.get("/historical")
async def historical(
    base: str = Query(...),
    quote: str = Query(...),
    period: str | None = Query(None, description="24h|7d|1m|3m|6m|1y|2y|5y"),
    start: date | None = Query(None),
    end: date | None = Query(None),
):
    end = end or date.today()
    if start is None:
        days = period_to_days(period) if period else 30
        start = end - timedelta(days=days)

    result = await data_service.get_series(base.upper(), quote.upper(), start, end)
    if result.error and not result.observations:
        raise HTTPException(502, result.error)

    import pandas as pd

    series = pd.Series(
        [r for _, r in result.observations],
        index=pd.DatetimeIndex([d for d, _ in result.observations]),
    ).sort_index()

    return {
        "base": base.upper(),
        "quote": quote.upper(),
        "start": start.isoformat(),
        "end": end.isoformat(),
        "provider": result.provider,
        "rate_kind": result.rate_kind,
        "warning": result.error,
        "points": series_to_points(series),
    }
