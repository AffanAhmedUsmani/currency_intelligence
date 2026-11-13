"""Historical/latest FX data retrieval with SQLite-backed caching and
request de-duplication.

Design notes (deliberate simplifications, documented rather than hidden):
  * Caching is at daily granularity, keyed by (base, quote, date). A series
    is considered "covered" for a requested [start, end] window if the
    cache has an observation within 4 days of each boundary (handles
    weekends/holidays without needing a trading-day calendar). Interior
    gaps are not independently re-verified once boundary coverage exists —
    acceptable for a single-user local app, called out in the README.
  * "Latest" lookups use a short-TTL in-memory cache (not persisted),
    since they're requested far more often than historical windows and are
    meant to reflect "now", not be archived.
  * In-flight identical requests are de-duplicated via an asyncio.Lock per
    (base, quote) key so concurrent card renders don't trigger N redundant
    upstream calls.
"""

import asyncio
import time
from datetime import date, timedelta
from dataclasses import dataclass, field

from sqlalchemy import select, delete

from app.config import settings
from app.db import RateObservation, get_session
from app.providers.aggregator import AggregatedProvider
from app.providers.base import ProviderError

_aggregator = AggregatedProvider()
_locks: dict[tuple[str, str], asyncio.Lock] = {}
_latest_cache: dict[str, tuple[float, dict, str, str]] = {}
_PROVIDER_RATE_KIND = {"frankfurter": "reference", "yahoo": "indicative", "identity": "reference"}


@dataclass
class SeriesResult:
    observations: list[tuple[date, float]] = field(default_factory=list)
    provider: str = "unknown"
    rate_kind: str = "reference"
    error: str | None = None


def _lock_for(base: str, quote: str) -> asyncio.Lock:
    key = (base, quote)
    if key not in _locks:
        _locks[key] = asyncio.Lock()
    return _locks[key]


def _cached_dates(base: str, quote: str, start: date, end: date) -> dict[date, float]:
    with get_session() as session:
        rows = session.execute(
            select(RateObservation.obs_date, RateObservation.rate).where(
                RateObservation.base == base,
                RateObservation.quote == quote,
                RateObservation.obs_date >= start,
                RateObservation.obs_date <= end,
            )
        ).all()
    return {r[0]: r[1] for r in rows}


def _covers_range(cached: dict[date, float], start: date, end: date) -> bool:
    if not cached:
        return False
    dates = list(cached.keys())
    has_near_start = any(start <= d <= start + timedelta(days=4) for d in dates)
    has_near_end = any(end - timedelta(days=4) <= d <= end for d in dates)
    return has_near_start and has_near_end


def _store(base: str, quote: str, provider: str, data: dict[date, float]) -> None:
    if not data:
        return
    with get_session() as session:
        existing = set(
            session.execute(
                select(RateObservation.obs_date).where(
                    RateObservation.base == base, RateObservation.quote == quote
                )
            ).scalars()
        )
        for d, rate in data.items():
            if d in existing:
                session.execute(
                    delete(RateObservation).where(
                        RateObservation.base == base,
                        RateObservation.quote == quote,
                        RateObservation.obs_date == d,
                    )
                )
            session.add(
                RateObservation(base=base, quote=quote, obs_date=d, rate=rate, provider=provider)
            )
        session.commit()


async def get_series(base: str, quote: str, start: date, end: date) -> SeriesResult:
    base, quote = base.upper(), quote.upper()
    if base == quote:
        days = (end - start).days + 1
        obs = [(start + timedelta(days=i), 1.0) for i in range(max(days, 1))]
        return SeriesResult(observations=obs, provider="identity", rate_kind="reference")

    async with _lock_for(base, quote):
        cached = _cached_dates(base, quote, start, end)
        if _covers_range(cached, start, end):
            obs = sorted((d, r) for d, r in cached.items() if start <= d <= end)
            provider = "cache"
            rate_kind = "reference"
            with get_session() as session:
                prov_row = session.execute(
                    select(RateObservation.provider).where(
                        RateObservation.base == base, RateObservation.quote == quote
                    ).limit(1)
                ).first()
                if prov_row:
                    provider = f"cache({prov_row[0]})"
                    rate_kind = _PROVIDER_RATE_KIND.get(prov_row[0], "reference")
            return SeriesResult(observations=obs, provider=provider, rate_kind=rate_kind)

        try:
            # Fetch a slightly wider window so boundary coverage is robust.
            result = await _aggregator.get_historical(
                base, quote, start - timedelta(days=5), end
            )
        except ProviderError as exc:
            if cached:
                obs = sorted((d, r) for d, r in cached.items() if start <= d <= end)
                return SeriesResult(
                    observations=obs, provider="cache(stale)", rate_kind="reference",
                    error=f"Could not refresh: {exc}",
                )
            return SeriesResult(error=str(exc))

        _store(base, quote, result.provider_name, result.data)
        obs = sorted((d, r) for d, r in result.data.items() if start <= d <= end)
        return SeriesResult(observations=obs, provider=result.provider_name, rate_kind=result.rate_kind)


async def get_many_series(
    base: str, quotes: list[str], start: date, end: date
) -> dict[str, SeriesResult]:
    results = await asyncio.gather(*[get_series(base, q, start, end) for q in quotes])
    return dict(zip(quotes, results))


async def get_latest(base: str, quotes: list[str]) -> tuple[dict[str, float], str, str]:
    base = base.upper()
    now = time.time()
    cache_key = base
    cached = _latest_cache.get(cache_key)
    if cached and (now - cached[0]) < settings.cache_latest_ttl_seconds:
        rates, provider, rate_kind = cached[1], cached[2], cached[3]
        missing = [q for q in quotes if q.upper() not in rates and q.upper() != base]
        if not missing:
            return rates, provider, rate_kind

    result = await _aggregator.get_latest(base, [q.upper() for q in quotes if q.upper() != base])
    rates = dict(result.data)
    rates[base] = 1.0
    _latest_cache[cache_key] = (now, rates, result.provider_name, result.rate_kind)
    return rates, result.provider_name, result.rate_kind
