"""Technical indicators computed from a daily close-price series.

Every provider available to this app (Frankfurter, Yahoo FX crosses)
returns daily *close* rates only — no intraday high/low/open. That matters:
ATR and the stochastic oscillator are textbook-defined on OHLC bars. Here
they're computed as close-based proxies (absolute daily change for ATR,
rolling min/max of the close for stochastic) and labeled as such everywhere
they surface in the API/UI, rather than silently presenting a proxy as the
canonical indicator.

All functions take a pandas Series indexed by date (ascending) and return a
Series aligned to the same index, with NaN wherever there isn't enough
history yet.
"""

import numpy as np
import pandas as pd


def sma(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window=window, min_periods=window).mean()


def ema(series: pd.Series, window: int) -> pd.Series:
    return series.ewm(span=window, adjust=False, min_periods=window).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Wilder's RSI."""
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    out = 100 - (100 / (1 + rs))
    out[avg_loss == 0] = 100.0
    return out


def macd(
    series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9
) -> tuple[pd.Series, pd.Series, pd.Series]:
    ema_fast = series.ewm(span=fast, adjust=False, min_periods=fast).mean()
    ema_slow = series.ewm(span=slow, adjust=False, min_periods=slow).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False, min_periods=signal).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def bollinger_bands(
    series: pd.Series, window: int = 20, num_std: float = 2.0
) -> tuple[pd.Series, pd.Series, pd.Series]:
    mid = sma(series, window)
    std = series.rolling(window=window, min_periods=window).std()
    upper = mid + num_std * std
    lower = mid - num_std * std
    return mid, upper, lower


def roc(series: pd.Series, period: int) -> pd.Series:
    """Rate of change, in percent."""
    return (series / series.shift(period) - 1.0) * 100.0


def momentum(series: pd.Series, period: int) -> pd.Series:
    return series - series.shift(period)


def atr_proxy(series: pd.Series, period: int = 14) -> pd.Series:
    """Close-to-close absolute-change proxy for Average True Range.

    Not a canonical OHLC ATR — see module docstring.
    """
    daily_range = series.diff().abs()
    return daily_range.rolling(window=period, min_periods=period).mean()


def stochastic_proxy(series: pd.Series, period: int = 14) -> pd.Series:
    """Close-based %K proxy: position of the close within its recent range."""
    low = series.rolling(window=period, min_periods=period).min()
    high = series.rolling(window=period, min_periods=period).max()
    denom = (high - low).replace(0, np.nan)
    return ((series - low) / denom) * 100.0
