"""Indicators are checked three ways: published reference values, naive
loop re-implementations written independently of the vectorised code, and a
truncation test proving no value depends on later bars."""

import numpy as np
import pandas as pd
import pytest

from backend.indicators import core
from backend.indicators.registry import INDICATORS, compute


@pytest.fixture(scope="module")
def candles() -> pd.DataFrame:
    rng = np.random.default_rng(7)
    n = 600
    close = 1.10 * np.exp(np.cumsum(rng.normal(0, 0.001, n)))
    open_ = np.concatenate(([1.10], close[:-1]))
    high = np.maximum(open_, close) + np.abs(rng.normal(0, 0.0004, n))
    low = np.minimum(open_, close) - np.abs(rng.normal(0, 0.0004, n))
    return pd.DataFrame(
        {
            "time": pd.date_range("2025-01-06", periods=n, freq="1h", tz="UTC"),
            "open": open_, "high": high, "low": low, "close": close,
            "tick_volume": 100, "spread": 12,
        }
    )


# --- naive references -------------------------------------------------------

def ref_seeded(values, period, alpha):
    out = [np.nan] * len(values)
    if len(values) >= period:
        out[period - 1] = sum(values[:period]) / period
        for i in range(period, len(values)):
            out[i] = out[i - 1] + alpha * (values[i] - out[i - 1])
    return np.array(out)


def ref_true_range(h, l, c):
    return [h[0] - l[0]] + [
        max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1])) for i in range(1, len(c))
    ]


def ref_rsi(close, period):
    gains = [max(close[i] - close[i - 1], 0) for i in range(1, len(close))]
    losses = [max(close[i - 1] - close[i], 0) for i in range(1, len(close))]
    g, l = ref_seeded(gains, period, 1 / period), ref_seeded(losses, period, 1 / period)
    return np.concatenate(([np.nan], 100 - 100 / (1 + g / l)))


def ref_adx(h, l, c, period):
    plus, minus, tr = [], [], ref_true_range(h, l, c)[1:]
    for i in range(1, len(c)):
        up, down = h[i] - h[i - 1], l[i - 1] - l[i]
        plus.append(up if up > down and up > 0 else 0.0)
        minus.append(down if down > up and down > 0 else 0.0)
    a = 1 / period
    str_, sp, sm = (ref_seeded(x, period, a) for x in (tr, plus, minus))
    pdi, mdi = 100 * sp / str_, 100 * sm / str_
    dx = 100 * np.abs(pdi - mdi) / (pdi + mdi)
    first = period - 1
    adx = np.concatenate((np.full(first, np.nan), ref_seeded(list(dx[first:]), period, a)))
    return np.concatenate(([np.nan], adx)), np.concatenate(([np.nan], pdi))


# --- tests ------------------------------------------------------------------

def test_sma_known_values():
    out = core.sma(pd.Series([1.0, 2, 3, 4, 5]), 3)
    assert out.isna().tolist() == [True, True, False, False, False]
    assert out.dropna().tolist() == [2.0, 3.0, 4.0]


def test_rsi_matches_wilder_published_example():
    # Widely reproduced 14-period worked example (StockCharts "RSI" article).
    close = pd.Series([
        44.34, 44.09, 44.15, 43.61, 44.33, 44.83, 45.10, 45.42, 45.84, 46.08,
        45.89, 46.03, 45.61, 46.28, 46.28, 46.00, 46.03, 46.41, 46.22, 45.64,
    ])
    out = core.rsi(close, 14)
    assert out.iloc[:14].isna().all()
    assert out.iloc[14:].round(2).tolist() == pytest.approx(
        [70.46, 66.25, 66.48, 69.35, 66.29, 57.92], abs=0.15
    )


def test_ema_and_wilder_match_reference(candles):
    c = candles["close"]
    np.testing.assert_allclose(core.ema(c, 20), ref_seeded(c.tolist(), 20, 2 / 21), rtol=1e-12)
    np.testing.assert_allclose(core.wilder(c, 14), ref_seeded(c.tolist(), 14, 1 / 14), rtol=1e-12)


def test_rsi_matches_reference(candles):
    c = candles["close"]
    np.testing.assert_allclose(core.rsi(c, 14), ref_rsi(c.tolist(), 14), rtol=1e-10)


def test_atr_matches_reference(candles):
    h, l, c = (candles[k].tolist() for k in ("high", "low", "close"))
    expected = ref_seeded(ref_true_range(h, l, c), 14, 1 / 14)
    np.testing.assert_allclose(core.atr(candles["high"], candles["low"], candles["close"], 14), expected, rtol=1e-12)


def test_adx_matches_reference(candles):
    h, l, c = (candles[k].tolist() for k in ("high", "low", "close"))
    adx_ref, pdi_ref = ref_adx(h, l, c, 14)
    out = core.adx(candles["high"], candles["low"], candles["close"], 14)
    np.testing.assert_allclose(out["plus_di"], pdi_ref, rtol=1e-10)
    np.testing.assert_allclose(out["adx"], adx_ref, rtol=1e-10)
    assert out["adx"].dropna().between(0, 100).all()


def test_macd_is_difference_of_emas(candles):
    c = candles["close"]
    out = core.macd(c, 12, 26, 9)
    np.testing.assert_allclose(out["macd"], core.ema(c, 12) - core.ema(c, 26), rtol=1e-12)
    assert out["signal"].first_valid_index() == 26 - 1 + 9 - 1
    with pytest.raises(ValueError):
        core.macd(c, 26, 12)


def test_bollinger_and_zscore(candles):
    c = candles["close"]
    b = core.bollinger(c, 20, 2.0)
    window = c.iloc[100:120]
    assert b["middle"].iloc[119] == pytest.approx(window.mean())
    assert b["upper"].iloc[119] == pytest.approx(window.mean() + 2 * window.std(ddof=0))
    assert core.zscore(c, 20).iloc[119] == pytest.approx((c.iloc[119] - window.mean()) / window.std(ddof=0))


def test_bounded_oscillators(candles):
    h, l, c = candles["high"], candles["low"], candles["close"]
    assert core.rsi(c).dropna().between(0, 100).all()
    assert core.stochastic(h, l, c).dropna().stack().between(0, 100).all()


def test_flat_market_edge_cases():
    flat = pd.Series([1.0] * 60)
    assert (core.rsi(flat, 14).dropna() == 50).all()
    assert (core.stochastic(flat, flat, flat)["k"].dropna() == 50).all()
    assert core.zscore(flat, 20).isna().all()
    assert core.adx(flat, flat, flat)["adx"].isna().all()  # no range: undefined, not zero


def test_donchian_and_supertrend(candles):
    h, l, c = candles["high"], candles["low"], candles["close"]
    d = core.donchian(h, l, 20)
    assert d["upper"].iloc[50] == h.iloc[31:51].max()
    assert d["lower"].iloc[50] == l.iloc[31:51].min()
    st = core.supertrend(h, l, c, 10, 3.0).dropna()
    assert set(st["direction"].unique()) <= {1.0, -1.0}
    up = st["direction"] == 1.0
    assert (st.loc[up, "supertrend"] <= c[st.index][up]).all()   # line below price in uptrend
    assert (st.loc[~up, "supertrend"] >= c[st.index][~up]).all()


def test_ichimoku_cloud_is_lagged_span(candles):
    out = core.ichimoku(candles["high"], candles["low"], candles["close"])
    assert "chikou" not in out.columns
    pd.testing.assert_series_equal(out["cloud_a"], out["span_a"].shift(26), check_names=False)


@pytest.mark.parametrize("name", sorted(INDICATORS))
def test_no_lookahead(name, candles):
    """Values on a truncated history must equal the same bars of the full history."""
    full = compute(name, candles)
    for cut in (150, 333):
        part = compute(name, candles.iloc[:cut])
        pd.testing.assert_frame_equal(part, full.iloc[:cut], check_exact=False, rtol=1e-9, atol=1e-12)


@pytest.mark.parametrize("name", sorted(INDICATORS))
def test_warmup_is_nan_then_valid(name, candles):
    out = compute(name, candles)
    assert len(out) == len(candles)
    assert out.iloc[0].isna().any()
    assert out.iloc[-1].notna().all()


def test_compute_validates_parameters(candles):
    with pytest.raises(KeyError):
        compute("nope", candles)
    with pytest.raises(ValueError):
        compute("rsi", candles, period=0)
    with pytest.raises(ValueError):
        compute("rsi", candles, length=14)
    with pytest.raises(ValueError):
        compute("bollinger", candles, num_std=-1)
