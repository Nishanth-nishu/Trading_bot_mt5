"""Indicator catalogue: a uniform way to compute any indicator from a candle
frame, used by the API, the feature engine and the no-lookahead test."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import pandas as pd

from backend.indicators import core


@dataclass(frozen=True)
class IndicatorSpec:
    name: str
    description: str
    function: Callable[..., pd.Series | pd.DataFrame]
    inputs: tuple[str, ...]
    defaults: dict[str, float]


def _spec(name, description, function, inputs, **defaults) -> IndicatorSpec:
    return IndicatorSpec(name, description, function, inputs, defaults)


_HLC = ("high", "low", "close")

INDICATORS: dict[str, IndicatorSpec] = {
    s.name: s
    for s in [
        _spec("sma", "Simple moving average", core.sma, ("close",), period=20),
        _spec("ema", "Exponential moving average (SMA-seeded)", core.ema, ("close",), period=20),
        _spec("rsi", "Relative Strength Index (Wilder)", core.rsi, ("close",), period=14),
        _spec("macd", "MACD line, signal, histogram", core.macd, ("close",), fast=12, slow=26, signal=9),
        _spec("atr", "Average True Range (Wilder)", core.atr, _HLC, period=14),
        _spec("adx", "ADX with +DI and -DI (Wilder)", core.adx, _HLC, period=14),
        _spec("bollinger", "Bollinger Bands, width, %B", core.bollinger, ("close",), period=20, num_std=2.0),
        _spec("stochastic", "Slow stochastic %K and %D", core.stochastic, _HLC, k_period=14, smooth=3, d_period=3),
        _spec("roc", "Rate of change (%)", core.roc, ("close",), period=10),
        _spec("donchian", "Donchian channel (includes current bar)", core.donchian, ("high", "low"), period=20),
        _spec("keltner", "Keltner channel", core.keltner, _HLC, period=20, atr_period=10, multiplier=2.0),
        _spec("supertrend", "Supertrend line and direction", core.supertrend, _HLC, period=10, multiplier=3.0),
        _spec("ichimoku", "Ichimoku (causal cloud; no chikou)", core.ichimoku, _HLC, tenkan=9, kijun=26, senkou_b=52, displacement=26),
        _spec("zscore", "Rolling z-score of close", core.zscore, ("close",), period=20),
        _spec("rolling_volatility", "Std of one-bar log returns", core.rolling_volatility, ("close",), period=20),
    ]
}


def compute(name: str, candles: pd.DataFrame, **params) -> pd.DataFrame:
    """Compute an indicator; always returns a DataFrame aligned to ``candles``."""
    spec = INDICATORS.get(name)
    if spec is None:
        raise KeyError(f"Unknown indicator: {name}")
    unknown = set(params) - set(spec.defaults)
    if unknown:
        raise ValueError(f"Unknown parameters for {name}: {sorted(unknown)}")
    merged = {**spec.defaults, **params}
    for key, default in spec.defaults.items():
        if isinstance(default, int):
            if int(merged[key]) != merged[key] or merged[key] < 1:
                raise ValueError(f"{name}.{key} must be a positive integer")
            merged[key] = int(merged[key])
        elif merged[key] <= 0:
            raise ValueError(f"{name}.{key} must be positive")
    result = spec.function(*(candles[c] for c in spec.inputs), **merged)
    return result.to_frame(name) if isinstance(result, pd.Series) else result
