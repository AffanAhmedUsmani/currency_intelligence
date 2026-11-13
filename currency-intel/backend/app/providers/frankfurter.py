"""Frankfurter provider — wraps the ECB daily reference rates (frankfurter.dev).

Free, keyless, no rate limit published, and the rates are genuine official
ECB daily reference rates (clearly a "reference" rate, not a tradable quote).
Its currency list is fixed by what the ECB publishes, which notably excludes
PKR and the Gulf currencies — `supports()` reflects that honestly so the
aggregator knows to fall back to another provider instead of silently
returning wrong data.
"""

from datetime import date

import httpx

from app.providers.base import ProviderError, RateProvider

_BASE_URL = "https://api.frankfurter.dev/v1"

SUPPORTED = {
    "AUD", "BGN", "BRL", "CAD", "CHF", "CNY", "CZK", "DKK", "EUR", "GBP",
    "HKD", "HUF", "IDR", "ILS", "INR", "ISK", "JPY", "KRW", "MXN", "MYR",
    "NOK", "NZD", "PHP", "PLN", "RON", "SEK", "SGD", "THB", "TRY", "USD",
    "ZAR",
}


class FrankfurterProvider(RateProvider):
    name = "frankfurter"
    rate_kind = "reference"

    def __init__(self, timeout: float = 12.0):
        self._timeout = timeout

    def supports(self, code: str) -> bool:
        return code.upper() in SUPPORTED

    async def get_latest(self, base: str, quotes: list[str]) -> dict[str, float]:
        base = base.upper()
        usable = [q.upper() for q in quotes if self.supports(q) and q.upper() != base]
        if not usable:
            return {}
        params = {"from": base, "to": ",".join(usable)}
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.get(f"{_BASE_URL}/latest", params=params, timeout=self._timeout)
            except httpx.HTTPError as exc:
                raise ProviderError(f"frankfurter: network error: {exc}") from exc
        if resp.status_code != 200:
            raise ProviderError(f"frankfurter: HTTP {resp.status_code}")
        return resp.json().get("rates", {})

    async def get_historical(
        self, base: str, quote: str, start: date, end: date
    ) -> dict[date, float]:
        base, quote = base.upper(), quote.upper()
        if not (self.supports(base) and self.supports(quote)):
            raise ProviderError(f"frankfurter: unsupported pair {base}/{quote}")
        if base == quote:
            raise ProviderError("frankfurter: base equals quote")

        params = {"from": base, "to": quote}
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.get(
                    f"{_BASE_URL}/{start.isoformat()}..{end.isoformat()}",
                    params=params,
                    timeout=self._timeout,
                )
            except httpx.HTTPError as exc:
                raise ProviderError(f"frankfurter: network error: {exc}") from exc
        if resp.status_code != 200:
            raise ProviderError(f"frankfurter: HTTP {resp.status_code}")

        rates = resp.json().get("rates", {})
        out: dict[date, float] = {}
        for day_str, obj in rates.items():
            if quote in obj:
                out[date.fromisoformat(day_str)] = float(obj[quote])
        if not out:
            raise ProviderError(f"frankfurter: empty series for {base}/{quote}")
        return out
