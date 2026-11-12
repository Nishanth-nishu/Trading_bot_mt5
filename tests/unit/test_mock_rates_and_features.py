"""Mock candles are SIMULATED. These tests check the generator's plumbing
properties and the feature engine's causality, not market behaviour."""

from datetime import UTC, datetime

import numpy as np
import pandas as pd
import pytest

from backend.data.timeframes import Timeframe
from backend.features.engine import align_higher_timeframe, build_features
from backend.mt5.interface import MT5Error
from backend.mt5.mock import MockMT5Connector

START = datetime(2025, 3, 3, tzinfo=UTC)   # Monday
END = datetime(2025, 5, 5, tzinfo=UTC)


@pytest.fixture(scope="module")
def mock() -> MockMT5Connector:
    c = MockMT5Connector()
    c.connect()
    return c


def test_rates_are_deterministic_and_extend_without_changing(mock):
    a = mock.rates("EURUSD.m", "M5", START, END)
    fresh = MockMT5Connector()
    fresh.connect()
    longer = fresh.rates("EURUSD.m", "M5", START, datetime(2025, 8, 1, tzinfo=UTC))
    pd.testing.assert_frame_equal(a, longer.iloc[: len(a)])
    assert not a.equals(mock.rates("GBPUSD.m", "M5", START, END))


def test_rates_respect_range_weekends_and_ohlc(mock):
    df = mock.rates("EURUSD.m", "M5", START, END)
    assert df["time"].min() >= pd.Timestamp(START) and df["time"].max() < pd.Timestamp(END)
    assert df["time"].is_monotonic_increasing and df["time"].is_unique
    assert not (df["time"].dt.day_of_week == 5).any()  # no Saturday bars
    assert (df["high"] >= df[["open", "close"]].max(axis=1)).all()
    assert (df["low"] <= df[["open", "close"]].min(axis=1)).all()


def test_range_ending_mid_bar_keeps_complete_bars(mock):
    """Regression: a request ending mid-bar used to drop the last M5 bar and
    build higher-timeframe bars from truncated data."""
    mid_bar = datetime(2025, 4, 9, 14, 56, 16, tzinfo=UTC)
    m5 = mock.rates("EURUSD.m", "M5", START, mid_bar)
    assert m5["time"].max() == pd.Timestamp("2025-04-09 14:55", tz="UTC")
    h1_cut = mock.rates("EURUSD.m", "H1", START, mid_bar).iloc[-1]
    h1_full = mock.rates("EURUSD.m", "H1", START, END)
    pd.testing.assert_series_equal(
        h1_cut, h1_full[h1_full["time"] == h1_cut["time"]].iloc[0], check_names=False
    )


def test_never_returns_future_bars(mock):
    df = mock.rates("EURUSD.m", "H1", datetime(2026, 1, 1, tzinfo=UTC), datetime(2100, 1, 1, tzinfo=UTC))
    assert df["time"].max() <= pd.Timestamp.now("UTC")


def test_higher_timeframes_aggregate_the_m5_series(mock):
    m5 = mock.rates("USDJPY.m", "M5", START, END)
    h1 = mock.rates("USDJPY.m", "H1", START, END)
    bar = h1.iloc[40]
    inside = m5[(m5["time"] >= bar["time"]) & (m5["time"] < bar["time"] + pd.Timedelta(hours=1))]
    assert bar["open"] == inside["open"].iloc[0] and bar["close"] == inside["close"].iloc[-1]
    assert bar["high"] == inside["high"].max() and bar["low"] == inside["low"].min()
    assert bar["tick_volume"] == inside["tick_volume"].sum()


def test_unknown_symbol_and_timeframe(mock):
    with pytest.raises(MT5Error):
        mock.rates("EURUSD", "H1", START, END)
    with pytest.raises(ValueError):
        mock.rates("EURUSD.m", "D1", START, END)


def test_features_have_no_lookahead(mock):
    candles = mock.rates("EURUSD.m", "H1", START, END)
    full = build_features(candles)
    part = build_features(candles.iloc[:400])
    pd.testing.assert_frame_equal(part, full.iloc[:400], check_exact=False, rtol=1e-9, atol=1e-12)
    assert full.iloc[-1].notna().all()
    assert len(full) == len(candles)


def test_breakout_uses_previous_bars_channel(mock):
    candles = mock.rates("EURUSD.m", "H1", START, END)
    f = build_features(candles)
    i = 300
    prev_high = candles["high"].iloc[i - 20 : i].max()   # excludes bar i
    assert f["breakout_up"].iloc[i] == pytest.approx((candles["close"].iloc[i] - prev_high) / f["atr"].iloc[i])


def test_higher_timeframe_alignment_only_uses_closed_bars(mock):
    m15 = mock.rates("EURUSD.m", "M15", START, END)
    h4 = mock.rates("EURUSD.m", "H4", START, END)
    h4 = h4.assign(marker=np.arange(len(h4), dtype="float64"))
    out = align_higher_timeframe(m15, Timeframe.M15, h4, Timeframe.H4, ["marker"])
    assert len(out) == len(m15) and out["time"].equals(m15["time"])

    decision = out["time"] + pd.Timedelta(minutes=15)
    h4_close = (h4["time"] + pd.Timedelta(hours=4)).to_numpy()
    valid = out["H4_marker"].notna()
    assert valid.sum() > 0 and pd.isna(out["H4_marker"].iloc[0])  # nothing closed yet
    used_close = h4_close[out.loc[valid, "H4_marker"].astype(int).to_numpy()]
    assert (used_close <= decision[valid].to_numpy()).all()          # never a forming bar
    # ...and it is the latest closed one
    next_close = h4_close[np.minimum(out.loc[valid, "H4_marker"].astype(int).to_numpy() + 1, len(h4) - 1)]
    last = out.loc[valid, "H4_marker"].astype(int).to_numpy() == len(h4) - 1
    assert ((next_close > decision[valid].to_numpy()) | last).all()

    with pytest.raises(ValueError):
        align_higher_timeframe(h4, Timeframe.H4, m15, Timeframe.M15, ["close"])
