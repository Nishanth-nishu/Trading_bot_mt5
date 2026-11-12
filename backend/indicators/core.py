"""Technical indicators (own implementations; TA-Lib is not used).

Rules every function here obeys:

* Causal. The value at bar ``t`` depends only on bars ``<= t``. This is
  enforced by a truncation test over the whole registry.
* Warm-up is NaN. No value is emitted until the full lookback is available.
* Inputs are aligned pandas Series ordered by time. They may start with NaN
  (an indicator of an indicator) but must not contain NaN after the first
  valid value.

Conventions (they differ between platforms, so they are stated):

* EMA is seeded with the SMA of the first ``period`` values, alpha = 2/(period+1).
* Wilder smoothing (RSI, ATR, ADX) is seeded the same way, alpha = 1/period.
* The first bar's true range is high - low (no previous close exists).
* Standard deviations in Bollinger Bands and z-score are population (ddof=0).
* Channels (Donchian) include the current bar; a breakout test must compare
  against the previous bar's channel.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def _seeded_ewm(x: pd.Series, period: int, alpha: float) -> pd.Series:
    if period < 1:
        raise ValueError("period must be >= 1")
    values = x.to_numpy(dtype="float64")
    out = np.full(len(values), np.nan)
    valid = np.flatnonzero(~np.isnan(values))
    if valid.size:
        seed_at = valid[0] + period - 1
        if seed_at < len(values):
            tail = values[seed_at:].copy()
            tail[0] = values[valid[0] : seed_at + 1].mean()
            out[seed_at:] = pd.Series(tail).ewm(alpha=alpha, adjust=False).mean().to_numpy()
    return pd.Series(out, index=x.index)


def sma(x: pd.Series, period: int) -> pd.Series:
    return x.rolling(period, min_periods=period).mean()


def ema(x: pd.Series, period: int) -> pd.Series:
    return _seeded_ewm(x, period, 2.0 / (period + 1))


def wilder(x: pd.Series, period: int) -> pd.Series:
    return _seeded_ewm(x, period, 1.0 / period)


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = wilder(delta.clip(lower=0), period)
    loss = wilder(-delta.clip(upper=0), period)
    out = 100 - 100 / (1 + gain / loss)
    out = out.mask(loss == 0, 100.0).mask((loss == 0) & (gain == 0), 50.0)
    return out.where(gain.notna())


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    if fast >= slow:
        raise ValueError("fast must be < slow")
    line = ema(close, fast) - ema(close, slow)
    sig = ema(line, signal)
    return pd.DataFrame({"macd": line, "signal": sig, "histogram": line - sig})


def true_range(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    prev = close.shift(1)
    return pd.concat([high - low, (high - prev).abs(), (low - prev).abs()], axis=1).max(axis=1)


def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    return wilder(true_range(high, low, close), period)


def adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.DataFrame:
    up = high.diff()
    down = -low.diff()
    plus_dm = up.where((up > down) & (up > 0), 0.0).where(up.notna())
    minus_dm = down.where((down > up) & (down > 0), 0.0).where(down.notna())
    tr = true_range(high, low, close).where(up.notna())  # start at bar 1 with the DMs
    smoothed_tr = wilder(tr, period)
    plus_di = 100 * wilder(plus_dm, period) / smoothed_tr
    minus_di = 100 * wilder(minus_dm, period) / smoothed_tr
    total = plus_di + minus_di
    dx = (100 * (plus_di - minus_di).abs() / total).mask(total == 0, 0.0)
    return pd.DataFrame({"adx": wilder(dx, period), "plus_di": plus_di, "minus_di": minus_di})


def bollinger(close: pd.Series, period: int = 20, num_std: float = 2.0) -> pd.DataFrame:
    mid = sma(close, period)
    std = close.rolling(period, min_periods=period).std(ddof=0)
    upper, lower = mid + num_std * std, mid - num_std * std
    band = upper - lower
    return pd.DataFrame(
        {
            "middle": mid,
            "upper": upper,
            "lower": lower,
            "width": band / mid,
            "percent_b": ((close - lower) / band).where(band > 0),
        }
    )


def stochastic(
    high: pd.Series, low: pd.Series, close: pd.Series,
    k_period: int = 14, smooth: int = 3, d_period: int = 3,
) -> pd.DataFrame:
    highest = high.rolling(k_period, min_periods=k_period).max()
    lowest = low.rolling(k_period, min_periods=k_period).min()
    span = highest - lowest
    raw = (100 * (close - lowest) / span).where(span > 0, 50.0).where(span.notna())
    k = sma(raw, smooth)
    return pd.DataFrame({"k": k, "d": sma(k, d_period)})


def roc(close: pd.Series, period: int = 10) -> pd.Series:
    return 100 * (close / close.shift(period) - 1)


def donchian(high: pd.Series, low: pd.Series, period: int = 20) -> pd.DataFrame:
    upper = high.rolling(period, min_periods=period).max()
    lower = low.rolling(period, min_periods=period).min()
    return pd.DataFrame({"upper": upper, "lower": lower, "middle": (upper + lower) / 2})


def keltner(
    high: pd.Series, low: pd.Series, close: pd.Series,
    period: int = 20, atr_period: int = 10, multiplier: float = 2.0,
) -> pd.DataFrame:
    mid = ema(close, period)
    offset = multiplier * atr(high, low, close, atr_period)
    return pd.DataFrame({"middle": mid, "upper": mid + offset, "lower": mid - offset})


def supertrend(
    high: pd.Series, low: pd.Series, close: pd.Series,
    period: int = 10, multiplier: float = 3.0,
) -> pd.DataFrame:
    """direction: +1 uptrend, -1 downtrend, NaN during warm-up."""
    a = atr(high, low, close, period).to_numpy()
    hl2 = ((high + low) / 2).to_numpy()
    c = close.to_numpy()
    n = len(c)
    line = np.full(n, np.nan)
    direction = np.full(n, np.nan)
    upper = lower = np.nan
    for i in range(n):
        if np.isnan(a[i]):
            continue
        basic_upper, basic_lower = hl2[i] + multiplier * a[i], hl2[i] - multiplier * a[i]
        if np.isnan(upper):  # first bar with an ATR
            upper, lower = basic_upper, basic_lower
            direction[i] = 1.0 if c[i] >= hl2[i] else -1.0
        else:
            upper = basic_upper if (basic_upper < upper or c[i - 1] > upper) else upper
            lower = basic_lower if (basic_lower > lower or c[i - 1] < lower) else lower
            if direction[i - 1] == 1.0:
                direction[i] = -1.0 if c[i] < lower else 1.0
            else:
                direction[i] = 1.0 if c[i] > upper else -1.0
        line[i] = lower if direction[i] == 1.0 else upper
    return pd.DataFrame({"supertrend": line, "direction": direction}, index=close.index)


def ichimoku(
    high: pd.Series, low: pd.Series, close: pd.Series,
    tenkan: int = 9, kijun: int = 26, senkou_b: int = 52, displacement: int = 26,
) -> pd.DataFrame:
    """``cloud_a``/``cloud_b`` are the cloud in force AT each bar, i.e. the spans
    computed ``displacement`` bars earlier. The chikou span is omitted: plotted
    at its conventional position it would place a future close on a past bar."""

    def midpoint(period: int) -> pd.Series:
        return (
            high.rolling(period, min_periods=period).max()
            + low.rolling(period, min_periods=period).min()
        ) / 2

    t, k = midpoint(tenkan), midpoint(kijun)
    span_a, span_b = (t + k) / 2, midpoint(senkou_b)
    return pd.DataFrame(
        {
            "tenkan": t,
            "kijun": k,
            "span_a": span_a,
            "span_b": span_b,
            "cloud_a": span_a.shift(displacement),
            "cloud_b": span_b.shift(displacement),
        }
    )


def zscore(x: pd.Series, period: int = 20) -> pd.Series:
    std = x.rolling(period, min_periods=period).std(ddof=0)
    return ((x - sma(x, period)) / std).where(std > 0)


def log_returns(close: pd.Series, period: int = 1) -> pd.Series:
    return np.log(close / close.shift(period))


def rolling_volatility(close: pd.Series, period: int = 20) -> pd.Series:
    """Sample standard deviation of one-bar log returns (per bar, not annualised)."""
    return log_returns(close).rolling(period, min_periods=period).std(ddof=1)
