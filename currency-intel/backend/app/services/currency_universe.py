"""Configurable currency universe metadata.

This is intentionally larger than the ~20 currencies mentioned in the product
brief so the comparison universe can be expanded without code changes to the
analytics engine. Each entry carries metadata used for display and for the
"meaningful selection methodology" (liquidity tier feeds the volatility /
relevance based universe-selection logic in services/data_service.py).

liquidity_tier: 1 = most heavily traded / reserve currencies, 2 = actively
traded regional currencies, 3 = thinly traded / pegged or restricted.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class CurrencyMeta:
    code: str
    name: str
    flag: str
    liquidity_tier: int


CURRENCIES: dict[str, CurrencyMeta] = {
    m.code: m
    for m in [
        CurrencyMeta("USD", "US Dollar", "🇺🇸", 1),
        CurrencyMeta("EUR", "Euro", "🇪🇺", 1),
        CurrencyMeta("GBP", "British Pound", "🇬🇧", 1),
        CurrencyMeta("JPY", "Japanese Yen", "🇯🇵", 1),
        CurrencyMeta("CHF", "Swiss Franc", "🇨🇭", 1),
        CurrencyMeta("AUD", "Australian Dollar", "🇦🇺", 1),
        CurrencyMeta("CAD", "Canadian Dollar", "🇨🇦", 1),
        CurrencyMeta("CNY", "Chinese Yuan", "🇨🇳", 1),
        CurrencyMeta("NZD", "New Zealand Dollar", "🇳🇿", 2),
        CurrencyMeta("SGD", "Singapore Dollar", "🇸🇬", 2),
        CurrencyMeta("HKD", "Hong Kong Dollar", "🇭🇰", 2),
        CurrencyMeta("SEK", "Swedish Krona", "🇸🇪", 2),
        CurrencyMeta("NOK", "Norwegian Krone", "🇳🇴", 2),
        CurrencyMeta("DKK", "Danish Krone", "🇩🇰", 2),
        CurrencyMeta("PLN", "Polish Zloty", "🇵🇱", 2),
        CurrencyMeta("INR", "Indian Rupee", "🇮🇳", 2),
        CurrencyMeta("TRY", "Turkish Lira", "🇹🇷", 2),
        CurrencyMeta("MYR", "Malaysian Ringgit", "🇲🇾", 2),
        CurrencyMeta("THB", "Thai Baht", "🇹🇭", 2),
        CurrencyMeta("ZAR", "South African Rand", "🇿🇦", 2),
        CurrencyMeta("MXN", "Mexican Peso", "🇲🇽", 2),
        CurrencyMeta("BRL", "Brazilian Real", "🇧🇷", 2),
        CurrencyMeta("KRW", "South Korean Won", "🇰🇷", 2),
        CurrencyMeta("IDR", "Indonesian Rupiah", "🇮🇩", 2),
        CurrencyMeta("PHP", "Philippine Peso", "🇵🇭", 2),
        CurrencyMeta("AED", "UAE Dirham", "🇦🇪", 3),
        CurrencyMeta("SAR", "Saudi Riyal", "🇸🇦", 3),
        CurrencyMeta("QAR", "Qatari Riyal", "🇶🇦", 3),
        CurrencyMeta("KWD", "Kuwaiti Dinar", "🇰🇼", 3),
        CurrencyMeta("OMR", "Omani Rial", "🇴🇲", 3),
        CurrencyMeta("BHD", "Bahraini Dinar", "🇧🇭", 3),
        CurrencyMeta("PKR", "Pakistani Rupee", "🇵🇰", 2),
        CurrencyMeta("EGP", "Egyptian Pound", "🇪🇬", 3),
        CurrencyMeta("NGN", "Nigerian Naira", "🇳🇬", 3),
        CurrencyMeta("LKR", "Sri Lankan Rupee", "🇱🇰", 3),
        CurrencyMeta("BDT", "Bangladeshi Taka", "🇧🇩", 3),
        CurrencyMeta("VND", "Vietnamese Dong", "🇻🇳", 3),
        CurrencyMeta("RUB", "Russian Ruble", "🇷🇺", 3),
        CurrencyMeta("ILS", "Israeli Shekel", "🇮🇱", 2),
        CurrencyMeta("CZK", "Czech Koruna", "🇨🇿", 2),
        CurrencyMeta("HUF", "Hungarian Forint", "🇭🇺", 2),
    ]
}

# Default comparison universe mirrors the product brief's ~20 majors,
# used when a base currency has no stronger relevance signal available.
DEFAULT_MAJORS = [
    "USD", "EUR", "GBP", "AUD", "CAD", "AED", "SAR", "CNY", "JPY", "CHF",
    "NZD", "SGD", "INR", "TRY", "MYR", "QAR", "KWD", "OMR", "BHD", "HKD",
]


def all_codes() -> list[str]:
    return list(CURRENCIES.keys())


def get_meta(code: str) -> CurrencyMeta:
    code = code.upper()
    if code in CURRENCIES:
        return CURRENCIES[code]
    return CurrencyMeta(code, code, "🏳️", 3)
