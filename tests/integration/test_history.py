"""Historical data manager and data API, against the MOCK adapter."""

from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import pytest
from sqlalchemy import update

from backend.data.history import DatasetUnusable, DataUnavailable
from backend.database.models import HistoricalDataMetadata

T1 = datetime(2026, 9, 2, 10, 30, tzinfo=UTC)   # a Wednesday, mid-bar
T2 = datetime(2026, 9, 9, 13, 0, tzinfo=UTC)


@pytest.fixture
def history(client):
    client.post("/api/mt5/connect")
    return client.app.state.history


def test_first_download_covers_target_and_stores_closed_bars_only(history):
    meta = history.update("EURUSD.m", "H1", now=T1)
    assert meta.source == "mock" and meta.canonical == "EURUSD"
    assert meta.meets_target and meta.quality_status == "ok"
    assert Path(meta.file_path).exists() and "mock__" in meta.file_path
    df = history.load(meta.id)
    assert df["time"].is_unique and df["time"].is_monotonic_increasing
    # 10:00 bar is still forming at 10:30 and must not be stored
    assert df["time"].max() == pd.Timestamp("2026-09-02 09:00", tz="UTC")


def test_incremental_update_appends_without_rewriting_history(history):
    first = history.update("EURUSD.m", "H1", now=T1)
    before = history.load(first.id)
    second = history.update("EURUSD.m", "H1", now=T2)
    after = history.load(second.id)
    assert second.id == first.id                      # same dataset row, updated
    assert len(after) > len(before)
    pd.testing.assert_frame_equal(after.iloc[: len(before)], before)
    assert after["time"].is_unique
    assert after["time"].max() == pd.Timestamp("2026-09-09 12:00", tz="UTC")
    # a repeat at the same instant adds nothing
    assert history.update("EURUSD.m", "H1", now=T2).bar_count == len(after)


def test_all_four_timeframes(history):
    for tf in ("M5", "M15", "H1", "H4"):
        meta = history.update("GBPUSD.m", tf, now=T1)
        assert meta.quality_status == "ok", (tf, meta.quality_report)
    assert len(history.datasets()) == 4


def test_unaligned_download_time_leaves_no_gaps(history):
    """Regression: chunked downloads at an arbitrary clock time must be gap-free."""
    now = datetime(2026, 9, 2, 10, 56, 16, 345000, tzinfo=UTC)
    for tf in ("M5", "H1"):
        meta = history.update("USDCAD.m", tf, now=now)
        assert meta.quality_status == "ok", meta.quality_report
    one_shot = client_rates(history, "USDCAD.m", "H1", now)
    pd.testing.assert_frame_equal(history.load(history.datasets()[-1].id), one_shot)


def client_rates(history, symbol, tf, now):
    """The same range fetched in a single request, closed bars only."""
    df = history._connector.rates(symbol, tf, datetime(2024, 1, 1, tzinfo=UTC), now)
    start = pd.Timestamp(now) - pd.DateOffset(months=24) - pd.Timedelta(days=7)
    df = df[(df["time"] >= start) & (df["time"] + pd.Timedelta(hours=1) <= pd.Timestamp(now))]
    return df.reset_index(drop=True)


def test_unknown_symbol(history):
    with pytest.raises(DataUnavailable):
        history.update("EURUSD", "H1", now=T1)   # bare name is not offered by this broker


def test_failed_datasets_are_refused(history, client):
    meta = history.update("EURUSD.m", "H4", now=T1)
    with client.app.state.sessions() as session:
        session.execute(update(HistoricalDataMetadata).values(quality_status="fail"))
        session.commit()
    with pytest.raises(DatasetUnusable):
        history.load(meta.id)
    assert len(history.load(meta.id, require_usable=False)) == meta.bar_count


def test_data_api(client):
    assert client.post("/api/data/update", json={"symbol": "EURUSD.m"}).status_code == 409
    client.post("/api/mt5/connect")

    body = client.post("/api/data/update", json={"symbol": "EURUSD.m", "timeframes": ["H1", "H4"]}).json()
    assert [d["timeframe"] for d in body["datasets"]] == ["H1", "H4"] and body["errors"] == []
    dataset = body["datasets"][0]
    assert dataset["is_simulated"] is True and dataset["meets_target"] is True

    assert client.post("/api/data/update", json={"symbol": "NOPE"}).status_code == 502
    assert client.post("/api/data/update", json={"symbol": "EURUSD.m", "timeframes": ["D1"]}).status_code == 422

    listed = client.get("/api/data/datasets").json()
    assert len(listed) == 2

    candles = client.get("/api/mt5/historical", params={"dataset_id": dataset["id"], "limit": 50}).json()
    assert candles["columns"][0] == "time" and len(candles["rows"]) == 50
    assert candles["rows"][-1][0].endswith("Z")

    features = client.get("/api/data/features", params={"dataset_id": dataset["id"], "limit": 5}).json()
    assert "adx" in features["columns"] and len(features["rows"]) == 5
    assert features["feature_set_version"] == "1"

    assert client.get("/api/mt5/historical", params={"dataset_id": 9999}).status_code == 404
    assert client.get("/api/mt5/historical", params={"dataset_id": dataset["id"], "limit": 0}).status_code == 422

    names = {i["name"] for i in client.get("/api/indicators").json()}
    assert {"ema", "rsi", "macd", "atr", "adx", "bollinger", "supertrend", "ichimoku"} <= names
