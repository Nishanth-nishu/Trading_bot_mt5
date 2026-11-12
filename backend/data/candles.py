"""Canonical candle frame.

One row per bar. ``time`` is the bar OPEN time, timezone-aware UTC. A bar's
information is complete only at ``time + timeframe``; that close time is the
decision timestamp used everywhere downstream.
"""

from __future__ import annotations

import pandas as pd

CANDLE_COLUMNS = ("time", "open", "high", "low", "close", "tick_volume", "spread")
PRICE_COLUMNS = ("open", "high", "low", "close")


def empty_candles() -> pd.DataFrame:
    return normalise_candles(
        pd.DataFrame({c: [] for c in CANDLE_COLUMNS}).assign(
            time=pd.to_datetime([], utc=True)
        )
    )


def normalise_candles(df: pd.DataFrame) -> pd.DataFrame:
    """Select and type the canonical columns. Never alters prices or drops rows."""
    missing = [c for c in CANDLE_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Candle frame is missing columns: {missing}")
    out = df[list(CANDLE_COLUMNS)].copy()
    if not isinstance(out["time"].dtype, pd.DatetimeTZDtype):
        raise ValueError("Candle 'time' must be timezone-aware; naive timestamps are rejected.")
    out["time"] = out["time"].dt.tz_convert("UTC").dt.as_unit("ns")
    for col in PRICE_COLUMNS:
        out[col] = out[col].astype("float64")
    out["tick_volume"] = out["tick_volume"].astype("int64")
    out["spread"] = out["spread"].astype("int64")
    return out.reset_index(drop=True)
