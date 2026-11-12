"""Time helpers. The backend stores and exchanges UTC only."""

from __future__ import annotations

from datetime import UTC, datetime


def utc_now() -> datetime:
    return datetime.now(UTC)
