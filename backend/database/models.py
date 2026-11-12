"""SQLAlchemy models.

Phase 0 holds only the tables the foundation needs. The remaining entities
from spec section 25 are added, with migrations, in the phase that first
uses them (see docs/known-limitations.md).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from backend.core.timeutil import utc_now


class Base(DeclarativeBase):
    pass


class SystemState(Base):
    """Single-row table (id=1) holding persisted operating state."""

    __tablename__ = "system_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    operating_mode: Mapped[str] = mapped_column(String(32), nullable=False, default="research")
    kill_switch_engaged: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )


class HistoricalDataMetadata(Base):
    """One cached candle dataset per (source, server, symbol, timeframe)."""

    __tablename__ = "historical_data_metadata"
    __table_args__ = (
        UniqueConstraint("source", "broker_server", "symbol", "timeframe", name="uq_dataset"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(16), nullable=False)  # mock | real
    broker_server: Mapped[str] = mapped_column(String(128), nullable=False)
    symbol: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    canonical: Mapped[str] = mapped_column(String(16), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(8), nullable=False)
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)
    bar_count: Mapped[int] = mapped_column(Integer, nullable=False)
    first_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    coverage_months: Mapped[float] = mapped_column(Float, nullable=False)
    meets_target: Mapped[bool] = mapped_column(Boolean, nullable=False)
    meets_minimum: Mapped[bool] = mapped_column(Boolean, nullable=False)
    quality_status: Mapped[str] = mapped_column(String(16), nullable=False)
    quality_report: Mapped[str] = mapped_column(Text, nullable=False)  # JSON
    time_basis: Mapped[str] = mapped_column(String(48), nullable=False)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AuditLog(Base):
    """Append-only audit trail. Rows are never updated or deleted by the app."""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, index=True
    )
    category: Mapped[str] = mapped_column(String(48), nullable=False, index=True)
    event: Mapped[str] = mapped_column(String(96), nullable=False)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
