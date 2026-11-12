"""Historical data, indicator and feature endpoints."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pandas as pd
from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from backend.config.settings import Settings
from backend.data.history import DataUnavailable, HistoryManager
from backend.data.timeframes import Timeframe
from backend.database.models import HistoricalDataMetadata
from backend.features.engine import FEATURE_SET_VERSION, FeatureConfig, build_features
from backend.indicators.registry import INDICATORS
from backend.mt5.interface import MT5Error


class DatasetOut(BaseModel):
    id: int
    source: str
    is_simulated: bool
    broker_server: str
    symbol: str
    canonical: str
    timeframe: str
    bar_count: int
    first_time: datetime | None
    last_time: datetime | None
    coverage_months: float
    meets_target: bool
    meets_minimum: bool
    quality_status: str
    failures: list[str]
    warnings: list[str]
    time_basis: str
    retrieved_at: datetime


class UpdateRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=64)
    timeframes: list[Timeframe] | None = None


class UpdateResponse(BaseModel):
    datasets: list[DatasetOut]
    errors: list[str]


class CandlesResponse(BaseModel):
    dataset: DatasetOut
    columns: list[str]
    rows: list[list]


class IndicatorOut(BaseModel):
    name: str
    description: str
    inputs: list[str]
    defaults: dict[str, float]


class FeaturesResponse(BaseModel):
    dataset: DatasetOut
    feature_set_version: str
    config: dict
    columns: list[str]
    rows: list[list]


def _utc(value: datetime | None) -> datetime | None:
    # SQLite returns naive datetimes; everything stored is UTC.
    return value if value is None or value.tzinfo else value.replace(tzinfo=UTC)


def dataset_out(row: HistoricalDataMetadata) -> DatasetOut:
    report = json.loads(row.quality_report)
    return DatasetOut(
        id=row.id,
        source=row.source,
        is_simulated=row.source != "real",
        broker_server=row.broker_server,
        symbol=row.symbol,
        canonical=row.canonical,
        timeframe=row.timeframe,
        bar_count=row.bar_count,
        first_time=_utc(row.first_time),
        last_time=_utc(row.last_time),
        coverage_months=row.coverage_months,
        meets_target=row.meets_target,
        meets_minimum=row.meets_minimum,
        quality_status=row.quality_status,
        failures=report.get("failures", []),
        warnings=report.get("warnings", []),
        time_basis=row.time_basis,
        retrieved_at=_utc(row.retrieved_at),
    )


def _rows(frame: pd.DataFrame) -> list[list]:
    out = frame.copy()
    out["time"] = out["time"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    return out.astype(object).where(out.notna(), None).values.tolist()


def build_data_router(settings: Settings) -> APIRouter:
    router = APIRouter(prefix="/api")

    def history(request: Request) -> HistoryManager:
        return request.app.state.history

    def loaded(request: Request, dataset_id: int, limit: int):
        manager = history(request)
        meta = manager.dataset(dataset_id)
        if meta is None:
            raise HTTPException(status_code=404, detail="Dataset not found.")
        try:
            # Inspection endpoints may show failed datasets; they are labelled.
            frame = manager.load(dataset_id, require_usable=False)
        except DataUnavailable as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return meta, frame, limit

    @router.get("/data/datasets", response_model=list[DatasetOut], tags=["data"])
    def datasets(request: Request):
        return [dataset_out(row) for row in history(request).datasets()]

    @router.post("/data/update", response_model=UpdateResponse, tags=["data"])
    def update(request: Request, body: UpdateRequest):
        if not request.app.state.connector.is_connected():
            raise HTTPException(status_code=409, detail="MT5 is not connected.")
        timeframes = body.timeframes or [Timeframe(t) for t in settings.timeframes]
        done, errors = [], []
        for tf in timeframes:
            try:
                done.append(dataset_out(history(request).update(body.symbol, tf)))
            except (DataUnavailable, MT5Error) as exc:
                errors.append(f"{tf.value}: {exc}")
        if not done and errors:
            raise HTTPException(status_code=502, detail="; ".join(errors))
        return UpdateResponse(datasets=done, errors=errors)

    @router.get("/mt5/historical", response_model=CandlesResponse, tags=["data"])
    def historical(
        request: Request,
        dataset_id: int,
        limit: int = Query(500, ge=1, le=5000),
    ):
        meta, frame, limit = loaded(request, dataset_id, limit)
        tail = frame.tail(limit)
        return CandlesResponse(dataset=dataset_out(meta), columns=list(tail.columns), rows=_rows(tail))

    @router.get("/data/features", response_model=FeaturesResponse, tags=["data"])
    def features(
        request: Request,
        dataset_id: int,
        limit: int = Query(200, ge=1, le=5000),
    ):
        meta, frame, limit = loaded(request, dataset_id, limit)
        config = FeatureConfig()
        tail = build_features(frame, config).tail(limit)
        return FeaturesResponse(
            dataset=dataset_out(meta),
            feature_set_version=FEATURE_SET_VERSION,
            config=config.to_dict(),
            columns=list(tail.columns),
            rows=_rows(tail),
        )

    @router.get("/indicators", response_model=list[IndicatorOut], tags=["data"])
    def indicators():
        return [
            IndicatorOut(name=s.name, description=s.description, inputs=list(s.inputs), defaults=s.defaults)
            for s in INDICATORS.values()
        ]

    return router
