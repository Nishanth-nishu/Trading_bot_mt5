"""Broker-neutral MT5 connector contract.

Everything outside ``backend.mt5`` depends on this interface only, never on
the ``MetaTrader5`` module. Phase 0/1 scope is read-only: there is no order
submission method on the interface yet (added in Phase 9 behind the risk
engine and the demo guard).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pandas as pd


class MT5Error(Exception):
    """Connector failure. ``code`` carries the MT5 error code when known."""

    def __init__(self, message: str, code: int | None = None):
        super().__init__(message)
        self.code = code


class NotConnectedError(MT5Error):
    pass


class AccountTradeMode(StrEnum):
    DEMO = "demo"
    CONTEST = "contest"
    REAL = "real"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class TerminalInfo:
    name: str
    company: str
    build: int | None
    connected: bool
    trade_allowed: bool


@dataclass(frozen=True)
class AccountInfo:
    login: int
    server: str
    company: str
    currency: str
    leverage: int
    balance: float
    equity: float
    margin: float
    margin_free: float
    margin_level: float | None
    trade_mode: AccountTradeMode


@dataclass(frozen=True)
class SymbolSpec:
    """Broker-provided specification. ``name`` is the broker's exact symbol
    (may carry a suffix such as ``EURUSD.a``); ``canonical`` is base+quote."""

    name: str
    canonical: str
    currency_base: str
    currency_profit: str
    currency_margin: str
    digits: int
    point: float
    tick_size: float
    tick_value: float
    contract_size: float
    volume_min: float
    volume_max: float
    volume_step: float
    spread_points: int
    trade_allowed: bool
    path: str


@dataclass(frozen=True)
class Tick:
    symbol: str
    time: datetime  # UTC
    bid: float
    ask: float


class MT5Connector(ABC):
    """Abstract connector. Implementations: MockMT5Connector, RealMT5Connector."""

    #: "mock" or "real"; surfaced in every status response so simulated data
    #: can never be mistaken for a broker connection.
    kind: str

    #: How candle timestamps relate to UTC. "utc" means true UTC. Anything
    #: else is recorded with the dataset and raised as a data-quality warning.
    time_basis: str = "utc"

    @abstractmethod
    def rates(self, symbol: str, timeframe: str, start: datetime, end: datetime) -> "pd.DataFrame":
        """Candles with open time in [start, end) as a canonical candle frame
        (see backend.data.candles). May include the still-forming bar."""

    @abstractmethod
    def connect(self) -> None: ...

    @abstractmethod
    def disconnect(self) -> None: ...

    @abstractmethod
    def is_connected(self) -> bool: ...

    @abstractmethod
    def terminal_info(self) -> TerminalInfo: ...

    @abstractmethod
    def account_info(self) -> AccountInfo: ...

    @abstractmethod
    def forex_symbols(self) -> list[SymbolSpec]: ...

    @abstractmethod
    def tick(self, symbol: str) -> Tick: ...
