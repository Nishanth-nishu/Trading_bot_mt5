"""Supported timeframes."""

from __future__ import annotations

from enum import StrEnum

import pandas as pd


class Timeframe(StrEnum):
    M5 = "M5"
    M15 = "M15"
    H1 = "H1"
    H4 = "H4"

    @property
    def minutes(self) -> int:
        return {"M5": 5, "M15": 15, "H1": 60, "H4": 240}[self.value]

    @property
    def seconds(self) -> int:
        return self.minutes * 60

    @property
    def delta(self) -> pd.Timedelta:
        return pd.Timedelta(minutes=self.minutes)

    @property
    def pandas_freq(self) -> str:
        return f"{self.minutes}min"
