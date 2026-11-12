"""Historical data manager: download through the connector, cache as Parquet,
update incrementally, validate, and record provenance.

Datasets are stored per source (adapter kind + broker server), so simulated
candles can never be mixed with or mistaken for broker candles.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from backend.core.system_state import audit
from backend.core.timeutil import utc_now
from backend.data.candles import empty_candles, normalise_candles
from backend.data.quality import QualityReport, validate_candles
from backend.data.timeframes import Timeframe
from backend.database.models import HistoricalDataMetadata
from backend.mt5.interface import MT5Connector

FETCH_CHUNK = pd.Timedelta(days=90)
FETCH_MARGIN = pd.Timedelta(days=7)  # so weekends at either end do not shorten coverage


class DataUnavailable(Exception):
    pass


class DatasetUnusable(Exception):
    """Raised when a consumer asks for a dataset whose validation failed."""


def _safe(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", name)


class HistoryManager:
    def __init__(
        self,
        connector: MT5Connector,
        sessions: sessionmaker[Session],
        data_dir: Path,
        *,
        target_months: int = 24,
        minimum_months: int = 12,
    ):
        self._connector = connector
        self._sessions = sessions
        self._root = Path(data_dir) / "history"
        self._target_months = target_months
        self._minimum_months = minimum_months

    def _path(self, server: str, symbol: str, timeframe: Timeframe) -> Path:
        source = f"{self._connector.kind}__{_safe(server)}"
        return self._root / source / _safe(symbol) / f"{timeframe.value}.parquet"

    @staticmethod
    def _read(path: Path) -> pd.DataFrame:
        return normalise_candles(pd.read_parquet(path)) if path.exists() else empty_candles()

    @staticmethod
    def _write(path: Path, frame: pd.DataFrame) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".parquet.tmp")
        frame.to_parquet(tmp, index=False)
        os.replace(tmp, path)  # atomic: a crash never leaves a half-written dataset

    def update(
        self, symbol: str, timeframe: str | Timeframe, *, now: datetime | None = None
    ) -> HistoricalDataMetadata:
        """Download what is missing and re-validate. Only closed bars are stored."""
        tf = Timeframe(timeframe)
        now_ts = pd.Timestamp(now or utc_now())
        spec = next((s for s in self._connector.forex_symbols() if s.name == symbol), None)
        if spec is None:
            raise DataUnavailable(f"Symbol '{symbol}' is not offered by the connected broker.")
        server = self._connector.account_info().server
        path = self._path(server, symbol, tf)

        existing = self._read(path)
        if existing.empty:
            start = now_ts - pd.DateOffset(months=self._target_months) - FETCH_MARGIN
        else:
            start = existing["time"].max() + tf.delta

        parts = [existing]
        cursor = start
        while cursor < now_ts:
            chunk_end = min(cursor + FETCH_CHUNK, now_ts)
            parts.append(
                self._connector.rates(
                    symbol, tf.value, cursor.to_pydatetime(), chunk_end.to_pydatetime()
                )
            )
            cursor = chunk_end
        combined = pd.concat([p for p in parts if not p.empty], ignore_index=True) if any(
            not p.empty for p in parts
        ) else empty_candles()
        # Keep closed bars only; drop rows that are exact repeats. Conflicting
        # duplicates are kept and fail validation rather than being guessed at.
        combined = combined[combined["time"] + tf.delta <= now_ts].drop_duplicates()
        combined = normalise_candles(combined)
        if combined.empty:
            raise DataUnavailable(f"No {tf.value} candles returned for '{symbol}'.")

        self._write(path, combined)
        report = validate_candles(
            combined,
            tf,
            target_months=self._target_months,
            minimum_months=self._minimum_months,
            time_basis=self._connector.time_basis,
        )
        return self._record(server, symbol, spec.canonical, tf, path, report, now_ts, len(combined) - len(existing))

    def _record(
        self,
        server: str,
        symbol: str,
        canonical: str,
        tf: Timeframe,
        path: Path,
        report: QualityReport,
        retrieved_at: pd.Timestamp,
        added: int,
    ) -> HistoricalDataMetadata:
        with self._sessions() as session:
            row = session.scalar(
                select(HistoricalDataMetadata).where(
                    HistoricalDataMetadata.source == self._connector.kind,
                    HistoricalDataMetadata.broker_server == server,
                    HistoricalDataMetadata.symbol == symbol,
                    HistoricalDataMetadata.timeframe == tf.value,
                )
            )
            if row is None:
                row = HistoricalDataMetadata(
                    source=self._connector.kind,
                    broker_server=server,
                    symbol=symbol,
                    timeframe=tf.value,
                )
                session.add(row)
            row.canonical = canonical
            row.file_path = str(path)
            row.bar_count = report.bar_count
            row.first_time = pd.Timestamp(report.first_time).to_pydatetime()
            row.last_time = pd.Timestamp(report.last_time).to_pydatetime()
            row.coverage_months = report.coverage_months
            row.meets_target = report.meets_target
            row.meets_minimum = report.meets_minimum
            row.quality_status = report.status
            row.quality_report = json.dumps(report.to_dict())
            row.time_basis = report.time_basis
            row.retrieved_at = retrieved_at.to_pydatetime()
            audit(
                session,
                "data",
                "history_updated",
                f"{self._connector.kind}:{symbol}:{tf.value} +{added} bars, status={report.status}",
            )
            session.commit()
            return row

    def datasets(self) -> list[HistoricalDataMetadata]:
        with self._sessions() as session:
            return list(
                session.scalars(
                    select(HistoricalDataMetadata).order_by(
                        HistoricalDataMetadata.source,
                        HistoricalDataMetadata.symbol,
                        HistoricalDataMetadata.id,
                    )
                )
            )

    def dataset(self, dataset_id: int) -> HistoricalDataMetadata | None:
        with self._sessions() as session:
            return session.get(HistoricalDataMetadata, dataset_id)

    def load(self, dataset_id: int, *, require_usable: bool = True) -> pd.DataFrame:
        """Candles for research. Refuses datasets that failed validation unless
        the caller explicitly opts out (inspection only)."""
        meta = self.dataset(dataset_id)
        if meta is None or not Path(meta.file_path).exists():
            raise DataUnavailable(f"Dataset {dataset_id} is not cached.")
        if require_usable and meta.quality_status == "fail":
            raise DatasetUnusable(
                f"Dataset {dataset_id} ({meta.symbol} {meta.timeframe}) failed validation."
            )
        return self._read(Path(meta.file_path))
