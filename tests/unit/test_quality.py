import numpy as np
import pandas as pd
import pytest

from backend.data.candles import normalise_candles
from backend.data.quality import validate_candles
from backend.data.timeframes import Timeframe


def make(start="2025-01-06 00:00", periods=24 * 5, freq="1h", weeks=1) -> pd.DataFrame:
    """Clean H1 candles, Monday 00:00 to Friday 23:00, for ``weeks`` weeks."""
    times = pd.DatetimeIndex([])
    for w in range(weeks):
        times = times.append(
            pd.date_range(pd.Timestamp(start, tz="UTC") + pd.Timedelta(weeks=w), periods=periods, freq=freq)
        )
    n = len(times)
    close = 1.1 + 0.0001 * np.sin(np.arange(n))
    return normalise_candles(
        pd.DataFrame(
            {
                "time": times, "open": close, "high": close + 0.0002, "low": close - 0.0002,
                "close": close, "tick_volume": 100, "spread": 12,
            }
        )
    )


def check(df, **kw):
    return validate_candles(df, Timeframe.H1, **kw)


def test_clean_two_year_dataset_is_ok():
    r = check(make(weeks=105))
    assert r.status == "ok" and not r.failures and not r.warnings
    assert r.meets_target and r.meets_minimum
    assert r.weekend_gaps == 104 and r.unexpected_gaps == 0 and r.missing_bars_estimate == 0


def test_twelve_month_fallback_is_a_labelled_warning():
    r = check(make(weeks=60))
    assert r.status == "warning" and r.meets_minimum and not r.meets_target
    assert any("below the 24-month target" in w for w in r.warnings)


def test_below_minimum_history_fails():
    r = check(make(weeks=10))
    assert r.status == "fail" and not r.meets_minimum


def test_duplicates_fail():
    df = make(weeks=105)
    r = check(pd.concat([df, df.iloc[[5]]], ignore_index=True))
    assert r.duplicate_timestamps == 1 and r.status == "fail"


def test_out_of_order_fails():
    df = make(weeks=105)
    swapped = df.iloc[[1, 0] + list(range(2, len(df)))].reset_index(drop=True)
    assert check(swapped).out_of_order == 1


@pytest.mark.parametrize(
    "column,value", [("high", 1.0), ("low", 2.0), ("close", float("nan")), ("open", -1.0)]
)
def test_invalid_ohlc_fails(column, value):
    df = make(weeks=105)
    df.loc[10, column] = value
    r = check(df)
    assert r.invalid_ohlc == 1 and r.status == "fail"


def test_missing_bars_are_counted_not_filled():
    df = make(weeks=105)
    holed = df.drop(index=[30, 31, 32]).reset_index(drop=True)
    r = check(holed)
    assert r.unexpected_gaps == 1 and r.missing_bars_estimate == 3
    assert r.bar_count == len(df) - 3
    assert r.status == "warning"


def test_heavy_data_loss_fails():
    df = make(weeks=105)
    r = check(df.iloc[::2].reset_index(drop=True))
    assert r.missing_ratio > 0.10 and r.status == "fail"


def test_outlier_is_flagged_and_left_alone():
    df = make(weeks=105)
    df.loc[500, ["close", "high"]] = [1.3, 1.3]
    r = check(df)
    assert r.outlier_bars >= 1 and r.status == "warning"
    assert df.loc[500, "close"] == 1.3


def test_misaligned_and_missing_spread_warn():
    df = make(weeks=105)
    df.loc[7, "time"] += pd.Timedelta(minutes=7)
    df["spread"] = 0
    r = check(df)
    assert r.misaligned_timestamps == 1 and not r.spread_available
    assert len(r.warnings) >= 2


def test_non_utc_time_basis_warns():
    r = check(make(weeks=105), time_basis="broker_server_time_unconverted")
    assert r.status == "warning" and any("not verified UTC" in w for w in r.warnings)


def test_empty_fails():
    assert check(make(weeks=1).iloc[0:0]).status == "fail"


def test_naive_timestamps_are_rejected():
    df = make(weeks=1)
    df["time"] = df["time"].dt.tz_localize(None)
    with pytest.raises(ValueError):
        normalise_candles(df)
