"""Feature engineering for regime detection and strategies.

Every feature at row ``t`` uses only bars ``<= t`` and is therefore known at
that bar's close (``time + timeframe``). Price-distance features are
expressed in ATR units so they are comparable across symbols and timeframes.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import pandas as pd

from backend.data.timeframes import Timeframe
from backend.indicators import core

FEATURE_SET_VERSION = "1"


@dataclass(frozen=True)
class FeatureConfig:
    atr_period: int = 14
    adx_period: int = 14
    ema_fast: int = 20
    ema_slow: int = 50
    slope_bars: int = 5
    bollinger_period: int = 20
    bollinger_std: float = 2.0
    volatility_period: int = 20
    channel_period: int = 20
    baseline_period: int = 100  # lookback for "relative to recent history"

    def to_dict(self) -> dict:
        return {"version": FEATURE_SET_VERSION, **asdict(self)}


def build_features(candles: pd.DataFrame, config: FeatureConfig = FeatureConfig()) -> pd.DataFrame:
    """One feature row per candle, keyed by the candle's open ``time``."""
    c = config
    high, low, close = candles["high"], candles["low"], candles["close"]
    atr = core.atr(high, low, close, c.atr_period)
    atr_safe = atr.where(atr > 0)
    adx = core.adx(high, low, close, c.adx_period)
    ema_fast, ema_slow = core.ema(close, c.ema_fast), core.ema(close, c.ema_slow)
    bands = core.bollinger(close, c.bollinger_period, c.bollinger_std)
    channel = core.donchian(high, low, c.channel_period).shift(1)  # previous bar's channel
    spread = candles["spread"].astype("float64")
    spread_baseline = spread.rolling(c.baseline_period, min_periods=c.baseline_period).median()

    return pd.DataFrame(
        {
            "time": candles["time"],
            "atr": atr,
            "atr_ratio": atr / atr.rolling(c.baseline_period, min_periods=c.baseline_period).mean(),
            "adx": adx["adx"],
            "plus_di": adx["plus_di"],
            "minus_di": adx["minus_di"],
            "ema_fast": ema_fast,
            "ema_slow": ema_slow,
            "ma_slope": (ema_slow - ema_slow.shift(c.slope_bars)) / atr_safe,
            "ma_separation": (ema_fast - ema_slow) / atr_safe,
            "bb_width": bands["width"],
            "volatility": core.rolling_volatility(close, c.volatility_period),
            "return_1": core.log_returns(close, 1),
            "return_5": core.log_returns(close, 5),
            "return_20": core.log_returns(close, 20),
            "displacement": (close - bands["middle"]) / atr_safe,
            "breakout_up": (close - channel["upper"]) / atr_safe,
            "breakout_down": (channel["lower"] - close) / atr_safe,
            "spread_ratio": (spread / spread_baseline).where(spread_baseline > 0),
        }
    )


def align_higher_timeframe(
    lower: pd.DataFrame,
    lower_tf: Timeframe,
    higher: pd.DataFrame,
    higher_tf: Timeframe,
    columns: list[str],
) -> pd.DataFrame:
    """Attach higher-timeframe values to lower-timeframe rows without lookahead.

    A higher-timeframe bar opened at T is only complete at T + higher_tf. Each
    lower row (decided at its own close) therefore receives the most recent
    higher bar that had ALREADY CLOSED by then, never the one still forming.
    Added columns are prefixed with the higher timeframe, e.g. ``H4_adx``.
    """
    if higher_tf.seconds <= lower_tf.seconds:
        raise ValueError("higher_tf must be longer than lower_tf")
    left = lower.assign(_decision=lower["time"] + lower_tf.delta)
    right = higher[["time", *columns]].rename(columns={k: f"{higher_tf.value}_{k}" for k in columns})
    right = right.assign(_available=right["time"] + higher_tf.delta).drop(columns="time")
    merged = pd.merge_asof(
        left.sort_values("_decision"),
        right.sort_values("_available"),
        left_on="_decision",
        right_on="_available",
        direction="backward",
    )
    return merged.drop(columns=["_decision", "_available"]).reset_index(drop=True)
