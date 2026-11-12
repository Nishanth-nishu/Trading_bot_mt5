"""Candle data validation.

Detects and reports; never repairs. Missing bars are not filled, outliers
are not smoothed, duplicates are not resolved. A dataset whose status is
"fail" is refused by ``HistoryManager.load``.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

import numpy as np
import pandas as pd

from backend.data.timeframes import Timeframe

DAYS_PER_MONTH = 30.4375
_WEEK = 604_800
_SATURDAY_REF = 2 * 86_400  # 1970-01-03 00:00 UTC was a Saturday

OUTLIER_MULTIPLE = 25.0  # |log return| above this multiple of the median is flagged
MISSING_WARN_RATIO = 0.01
MISSING_FAIL_RATIO = 0.10
MAX_WEEKEND_GAP_SECONDS = int(3.5 * 86_400)


@dataclass
class QualityReport:
    status: str = "ok"  # ok | warning | fail
    bar_count: int = 0
    first_time: str | None = None
    last_time: str | None = None
    coverage_months: float = 0.0
    meets_target: bool = False
    meets_minimum: bool = False
    duplicate_timestamps: int = 0
    out_of_order: int = 0
    misaligned_timestamps: int = 0
    invalid_ohlc: int = 0
    outlier_bars: int = 0
    weekend_gaps: int = 0
    unexpected_gaps: int = 0
    missing_bars_estimate: int = 0
    missing_ratio: float = 0.0
    spread_available: bool = False
    time_basis: str = "utc"
    failures: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def validate_candles(
    df: pd.DataFrame,
    timeframe: Timeframe,
    *,
    target_months: int = 24,
    minimum_months: int = 12,
    time_basis: str = "utc",
) -> QualityReport:
    """``df`` must be a canonical candle frame (backend.data.candles)."""
    r = QualityReport(bar_count=len(df), time_basis=time_basis)
    if df.empty:
        r.status = "fail"
        r.failures.append("Dataset is empty.")
        return r

    t = df["time"]
    r.duplicate_timestamps = int(t.duplicated().sum())
    r.out_of_order = int((t.diff().dt.total_seconds() < 0).sum())

    epoch_s = t.astype("int64").to_numpy() // 1_000_000_000
    # Sub-hour bars must sit on their grid; hour-plus bars only on the hour,
    # because a broker's H4 boundaries follow its server clock.
    r.misaligned_timestamps = int((epoch_s % min(timeframe.seconds, 3600) != 0).sum())

    o, h, l, c = (df[k].to_numpy() for k in ("open", "high", "low", "close"))
    stacked = np.vstack([o, h, l, c])
    bad = (
        np.isnan(stacked).any(axis=0)
        | (stacked <= 0).any(axis=0)
        | (h < np.maximum(o, c))
        | (l > np.minimum(o, c))
    )
    r.invalid_ohlc = int(bad.sum())

    s = df.drop_duplicates("time").sort_values("time")
    ts = s["time"].astype("int64").to_numpy() // 1_000_000_000
    step = np.diff(ts)
    is_gap = step > timeframe.seconds
    week_pos = (ts - _SATURDAY_REF) % _WEEK
    crosses_weekend = (week_pos[1:] < week_pos[:-1]) | (step >= _WEEK)
    weekend = is_gap & crosses_weekend & (step <= MAX_WEEKEND_GAP_SECONDS)
    unexpected = is_gap & ~weekend
    r.weekend_gaps = int(weekend.sum())
    r.unexpected_gaps = int(unexpected.sum())
    r.missing_bars_estimate = int((step[unexpected] // timeframe.seconds - 1).sum())
    r.missing_ratio = round(
        r.missing_bars_estimate / (len(s) + r.missing_bars_estimate), 6
    )

    closes = s["close"].to_numpy()
    with np.errstate(divide="ignore", invalid="ignore"):
        log_ret = np.abs(np.diff(np.log(closes)))
    contiguous = log_ret[~is_gap & np.isfinite(log_ret)]
    positive = contiguous[contiguous > 0]
    if positive.size:
        r.outlier_bars = int((contiguous > OUTLIER_MULTIPLE * np.median(positive)).sum())

    r.spread_available = bool((df["spread"] > 0).any())

    first, last = s["time"].iloc[0], s["time"].iloc[-1]
    r.first_time, r.last_time = first.isoformat(), last.isoformat()
    span_days = (last - first + timeframe.delta).total_seconds() / 86_400
    r.coverage_months = round(span_days / DAYS_PER_MONTH, 2)
    r.meets_target = r.coverage_months >= target_months
    r.meets_minimum = r.coverage_months >= minimum_months

    if r.duplicate_timestamps:
        r.failures.append(f"{r.duplicate_timestamps} duplicate timestamps.")
    if r.out_of_order:
        r.failures.append(f"{r.out_of_order} bars out of time order.")
    if r.invalid_ohlc:
        r.failures.append(f"{r.invalid_ohlc} bars with invalid OHLC values.")
    if not r.meets_minimum:
        r.failures.append(
            f"Only {r.coverage_months} months of history; minimum is {minimum_months}."
        )
    if r.missing_ratio > MISSING_FAIL_RATIO:
        r.failures.append(f"{r.missing_ratio:.1%} of bars missing outside weekends.")

    if r.meets_minimum and not r.meets_target:
        r.warnings.append(
            f"{r.coverage_months} months of history: below the {target_months}-month target "
            f"(minimum {minimum_months} met). Evidence quality is lower."
        )
    if MISSING_WARN_RATIO < r.missing_ratio <= MISSING_FAIL_RATIO:
        r.warnings.append(f"{r.missing_ratio:.1%} of bars missing outside weekends.")
    elif r.unexpected_gaps and r.missing_ratio <= MISSING_WARN_RATIO:
        r.warnings.append(
            f"{r.unexpected_gaps} gaps outside weekends ({r.missing_bars_estimate} bars); not filled."
        )
    if r.misaligned_timestamps:
        r.warnings.append(f"{r.misaligned_timestamps} bars off the timeframe grid.")
    if r.outlier_bars:
        r.warnings.append(f"{r.outlier_bars} outlier bars flagged for review; not altered.")
    if not r.spread_available:
        r.warnings.append("No spread data; cost modelling will need an assumed spread.")
    if time_basis != "utc":
        r.warnings.append(
            f"Timestamps are '{time_basis}', not verified UTC. Session logic is unreliable."
        )

    r.status = "fail" if r.failures else "warning" if r.warnings else "ok"
    return r
