"""Yahoo Finance chart API provider.

Yahoo's public (unauthenticated) chart endpoint publishes FX cross rates for
virtually any currency pair, including currencies most "official" free FX
APIs omit (PKR, LKR, BDT, NGN, EGP, the Gulf pegged currencies, etc.). This
is the same endpoint the popular `yfinance` library scrapes; it is
unofficial and can change or rate-limit without notice, which is why it sits
behind the same `RateProvider` interface as the official Frankfurter/ECB
provider and the aggregator can fall back away from it.

Ticker convention used here: "USD{CCY}=X" always returns "how many units of
CCY per 1 USD" (a daily close). We pivot every base/quote pair through USD
so we only ever need one consistent ticker shape, then triangulate:

    rate(base -> quote) = rate(USD -> quote) / rate(USD -> base)

USD itself is treated as an identity series (1.0 on every date) rather than
fetched, since "USDUSD=X" is not a real ticker.
"""

from datetime import date, datetime, timedelta, timezone

import httpx

from app.providers.base import ProviderError, RateProvider

_BASE_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "application/json",
}


def _to_epoch(d: date) -> int:
    return int(datetime(d.year, d.month, d.day, tzinfo=timezone.utc).timestamp())


class YahooFinanceProvider(RateProvider):
    name = "yahoo"
    rate_kind = "indicative"

    def __init__(self, timeout: float = 12.0):
        self._timeout = timeout

    def supports(self, code: str) -> bool:
        return bool(code) and code.isalpha() and len(code) == 3

    async def _fetch_series(
        self, client: httpx.AsyncClient, ccy: str, start: date, end: date
    ) -> dict[date, float]:
        if ccy.upper() == "USD":
            days = (end - start).days + 1
            return {start + timedelta(days=i): 1.0 for i in range(max(days, 1))}

        symbol = f"USD{ccy.upper()}=X"
        params = {
            "period1": _to_epoch(start - timedelta(days=5)),
            "period2": _to_epoch(end + timedelta(days=1)),
            "interval": "1d",
        }
        try:
            resp = await client.get(
                _BASE_URL.format(symbol=symbol), params=params, headers=_HEADERS, timeout=self._timeout
            )
        except httpx.HTTPError as exc:
            raise ProviderError(f"yahoo: network error fetching {symbol}: {exc}") from exc

        if resp.status_code != 200:
            raise ProviderError(f"yahoo: HTTP {resp.status_code} fetching {symbol}")

        payload = resp.json()
        result = (payload.get("chart") or {}).get("result")
        if not result:
            err = (payload.get("chart") or {}).get("error")
            raise ProviderError(f"yahoo: no data for {symbol} ({err})")

        series = result[0]
        timestamps = series.get("timestamp") or []
        closes = ((series.get("indicators") or {}).get("quote") or [{}])[0].get("close") or []

        out: dict[date, float] = {}
        for ts, close in zip(timestamps, closes):
            if close is None:
                continue
            d = datetime.fromtimestamp(ts, tz=timezone.utc).date()
            out[d] = float(close)
        if not out:
            raise ProviderError(f"yahoo: empty series for {symbol}")
        return out

    async def get_historical(
        self, base: str, quote: str, start: date, end: date
    ) -> dict[date, float]:
        base, quote = base.upper(), quote.upper()
        async with httpx.AsyncClient() as client:
            usd_base = await self._fetch_series(client, base, start, end)
            usd_quote = (
                usd_base if quote == base else await self._fetch_series(client, quote, start, end)
            )

        common_dates = sorted(set(usd_base) & set(usd_quote))
        common_dates = [d for d in common_dates if start <= d <= end]
        if not common_dates:
            raise ProviderError(f"yahoo: no overlapping dates for {base}/{quote}")

        return {d: usd_quote[d] / usd_base[d] for d in common_dates}

    async def get_latest(self, base: str, quotes: list[str]) -> dict[str, float]:
        end = date.today()
        start = end - timedelta(days=10)
        out: dict[str, float] = {}
        async with httpx.AsyncClient() as client:
            usd_base = await self._fetch_series(client, base, start, end)
            last_base_date = max(usd_base)
            for q in quotes:
                try:
                    usd_q = await self._fetch_series(client, q, start, end)
                except ProviderError:
                    continue
                common = sorted(set(usd_base) & set(usd_q))
                if not common:
                    continue
                d = common[-1]
                out[q] = usd_q[d] / usd_base[d]
        if not out:
            raise ProviderError(f"yahoo: could not resolve any latest rates for base {base}")
        return out
