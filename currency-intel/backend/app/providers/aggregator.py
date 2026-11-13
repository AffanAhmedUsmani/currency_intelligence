"""Aggregates multiple RateProviders with ordered fallback.

Policy: prefer Frankfurter (official ECB reference rates) when both legs of
the pair are in its currency list, since it's the more authoritative source;
otherwise fall back to Yahoo (broader coverage, including PKR and the Gulf
currencies, but unofficial/indicative). This is a thin policy layer on top
of the `RateProvider` interface so a new provider can be added or the
ordering changed without touching the analytics engine.
"""

from datetime import date

from app.providers.base import ProviderError, RateProvider
from app.providers.frankfurter import FrankfurterProvider
from app.providers.yahoo import YahooFinanceProvider


class ProviderResult:
    def __init__(self, data, provider_name: str, rate_kind: str):
        self.data = data
        self.provider_name = provider_name
        self.rate_kind = rate_kind


class AggregatedProvider:
    def __init__(self, providers: list[RateProvider] | None = None):
        self.providers = providers or [FrankfurterProvider(), YahooFinanceProvider()]

    def _ordered_for_pair(self, base: str, quote: str) -> list[RateProvider]:
        preferred, rest = [], []
        for p in self.providers:
            if p.supports(base) and p.supports(quote):
                preferred.append(p)
            else:
                rest.append(p)
        return preferred + rest

    async def get_historical(self, base: str, quote: str, start: date, end: date) -> ProviderResult:
        errors = []
        for provider in self._ordered_for_pair(base, quote):
            try:
                data = await provider.get_historical(base, quote, start, end)
                return ProviderResult(data, provider.name, provider.rate_kind)
            except ProviderError as exc:
                errors.append(str(exc))
        raise ProviderError(f"No provider could serve {base}/{quote} historical: {errors}")

    async def get_latest(self, base: str, quotes: list[str]) -> ProviderResult:
        """Tries to get as many quotes as possible from the preferred provider,
        then fills in any missing ones from the next provider."""
        merged: dict[str, float] = {}
        provider_used: dict[str, str] = {}
        remaining = list(quotes)
        last_rate_kind = "reference"
        for provider in self.providers:
            if not remaining:
                break
            try:
                data = await provider.get_latest(base, remaining)
            except ProviderError:
                continue
            for code, rate in data.items():
                if code not in merged:
                    merged[code] = rate
                    provider_used[code] = provider.name
                    last_rate_kind = provider.rate_kind
            remaining = [q for q in remaining if q not in merged]
        if not merged:
            raise ProviderError(f"No provider could serve latest rates for base {base}")
        providers_str = ",".join(sorted(set(provider_used.values())))
        return ProviderResult(merged, providers_str, last_rate_kind)
