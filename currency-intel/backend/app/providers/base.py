from abc import ABC, abstractmethod
from datetime import date


class ProviderError(Exception):
    """Raised when a provider cannot fulfill a request (network, unsupported pair, etc.)."""


class RateProvider(ABC):
    """Abstraction over an external FX data source.

    Implementations must be honest about what kind of rate they return
    (daily reference vs indicative mid-market) via `rate_kind`.
    """

    name: str = "base"
    rate_kind: str = "reference"  # "reference" | "indicative"

    @abstractmethod
    async def get_latest(self, base: str, quotes: list[str]) -> dict[str, float]:
        """Return {quote_code: rate} for 1 unit of base, as of latest available date."""

    @abstractmethod
    async def get_historical(
        self, base: str, quote: str, start: date, end: date
    ) -> dict[date, float]:
        """Return {date: rate} for base->quote between start and end (inclusive), daily."""

    @abstractmethod
    def supports(self, code: str) -> bool:
        """Whether this provider has any chance of serving data for this currency code."""
