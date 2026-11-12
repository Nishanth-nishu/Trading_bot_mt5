"""Mock MT5 connector for development and tests.

SIMULATED DATA. Nothing here comes from a broker. The mock deliberately uses
a non-USD account currency and suffixed symbol names so code that assumes
USD or bare symbol names fails early.
"""

from __future__ import annotations

import math
import zlib
from datetime import datetime

import numpy as np
import pandas as pd

from backend.core.timeutil import utc_now
from backend.data.candles import empty_candles, normalise_candles
from backend.data.timeframes import Timeframe

_EPOCH_S = 1_704_067_200  # 2024-01-01 00:00 UTC (a Monday)

from backend.mt5.interface import (  # noqa: E402
    AccountInfo,
    AccountTradeMode,
    MT5Connector,
    MT5Error,
    NotConnectedError,
    SymbolSpec,
    TerminalInfo,
    Tick,
)

# canonical, digits, mid price, tick value in account currency (illustrative only)
_MOCK_PAIRS: list[tuple[str, int, float, float]] = [
    ("EURUSD", 5, 1.08500, 0.92),
    ("GBPUSD", 5, 1.27000, 0.92),
    ("USDJPY", 3, 151.500, 0.61),
    ("AUDUSD", 5, 0.65500, 0.92),
    ("USDCAD", 5, 1.36500, 0.67),
    ("USDCHF", 5, 0.88500, 1.04),
    ("EURJPY", 3, 164.400, 0.61),
    ("EURGBP", 5, 0.85400, 1.17),
]


class MockMT5Connector(MT5Connector):
    kind = "mock"

    def __init__(
        self,
        *,
        balance: float = 1000.0,
        currency: str = "EUR",
        trade_mode: AccountTradeMode = AccountTradeMode.DEMO,
        symbol_suffix: str = ".m",
        login: int = 90000001,
    ):
        self._connected = False
        self._balance = balance
        self._currency = currency
        self._trade_mode = trade_mode
        self._suffix = symbol_suffix
        self._login = login
        self._m5_cache: dict[str, tuple[int, pd.DataFrame]] = {}

    def connect(self) -> None:
        self._connected = True

    def disconnect(self) -> None:
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected

    def _require(self) -> None:
        if not self._connected:
            raise NotConnectedError("Mock MT5 connector is not connected.")

    def terminal_info(self) -> TerminalInfo:
        self._require()
        return TerminalInfo(
            name="Mock Terminal (simulated)",
            company="TradeLab mock",
            build=None,
            connected=True,
            trade_allowed=False,
        )

    def account_info(self) -> AccountInfo:
        self._require()
        return AccountInfo(
            login=self._login,
            server="Mock-Demo",
            company="TradeLab mock",
            currency=self._currency,
            leverage=30,
            balance=self._balance,
            equity=self._balance,
            margin=0.0,
            margin_free=self._balance,
            margin_level=None,
            trade_mode=self._trade_mode,
        )

    def forex_symbols(self) -> list[SymbolSpec]:
        self._require()
        specs = []
        for canonical, digits, _mid, tick_value in _MOCK_PAIRS:
            point = 10**-digits
            specs.append(
                SymbolSpec(
                    name=f"{canonical}{self._suffix}",
                    canonical=canonical,
                    currency_base=canonical[:3],
                    currency_profit=canonical[3:],
                    currency_margin=canonical[:3],
                    digits=digits,
                    point=point,
                    tick_size=point,
                    tick_value=tick_value,
                    contract_size=100_000.0,
                    volume_min=0.01,
                    volume_max=50.0,
                    volume_step=0.01,
                    spread_points=12,
                    trade_allowed=True,
                    path=f"Forex\\Mock\\{canonical}{self._suffix}",
                )
            )
        return specs

    # ------------------------------------------------------------------
    # Synthetic candles. A seeded random walk on a fixed M5 grid starting at
    # _EPOCH, closed from Friday 22:00 to Sunday 22:00 UTC. Higher timeframes
    # are aggregated from the M5 series so all timeframes agree. The same
    # symbol always yields the same history. This is NOT market data and has
    # no edge to find: results on it prove plumbing, never strategy quality.
    # ------------------------------------------------------------------

    def _m5(self, canonical: str, digits: int, mid: float, n_grid: int) -> pd.DataFrame:
        cached = self._m5_cache.get(canonical)
        if cached is not None and cached[0] >= n_grid:
            return cached[1]
        seed = zlib.crc32(canonical.encode())
        grid_s = _EPOCH_S + np.arange(n_grid, dtype=np.int64) * 300
        week_pos = (grid_s - 2 * 86400) % 604800  # seconds since Saturday 00:00 UTC
        is_open = (week_pos >= 86400 + 22 * 3600) & (week_pos < 6 * 86400 + 22 * 3600)

        sigma = 0.0003
        # Draw over the whole grid so a longer request extends, never changes, history.
        z = np.random.default_rng([seed, 1]).standard_normal(n_grid)
        wick_up = np.abs(np.random.default_rng([seed, 2]).standard_normal(n_grid))
        wick_dn = np.abs(np.random.default_rng([seed, 3]).standard_normal(n_grid))
        volume = np.random.default_rng([seed, 4]).integers(20, 400, n_grid)
        spread = 10 + np.random.default_rng([seed, 5]).integers(0, 5, n_grid)

        close = mid * np.exp(np.cumsum(np.where(is_open, sigma * z, 0.0)))
        open_ = np.concatenate(([mid], close[:-1]))
        high = np.maximum(open_, close) * (1 + wick_up * sigma * 0.5)
        low = np.minimum(open_, close) * (1 - wick_dn * sigma * 0.5)

        frame = pd.DataFrame(
            {
                "time": pd.to_datetime(grid_s[is_open], unit="s", utc=True),
                "open": np.round(open_[is_open], digits),
                "high": np.round(high[is_open], digits),
                "low": np.round(low[is_open], digits),
                "close": np.round(close[is_open], digits),
                "tick_volume": volume[is_open],
                "spread": spread[is_open],
            }
        )
        frame = normalise_candles(frame)
        self._m5_cache[canonical] = (n_grid, frame)
        return frame

    def rates(self, symbol: str, timeframe: str, start: datetime, end: datetime) -> pd.DataFrame:
        self._require()
        tf = Timeframe(timeframe)
        pair = next((p for p in _MOCK_PAIRS if f"{p[0]}{self._suffix}" == symbol), None)
        if pair is None:
            raise MT5Error(f"Unknown symbol: {symbol}")
        canonical, digits, mid, _tick_value = pair
        now = pd.Timestamp(utc_now())
        end = min(pd.Timestamp(end), now)  # never emit future bars
        start = pd.Timestamp(start)
        # Every M5 bar that has OPENED by now. Like a real terminal, a bar in the
        # past is always returned complete, whatever range the caller asked for;
        # only the bar forming right now can be partial.
        n_grid = math.ceil((now.timestamp() - _EPOCH_S) / 300)
        if n_grid <= 0 or start >= end:
            return empty_candles()
        m5 = self._m5(canonical, digits, mid, n_grid)
        m5 = m5[m5["time"] < now]
        if tf is not Timeframe.M5:
            m5 = (
                m5.groupby(m5["time"].dt.floor(tf.pandas_freq), sort=True)
                .agg(
                    open=("open", "first"),
                    high=("high", "max"),
                    low=("low", "min"),
                    close=("close", "last"),
                    tick_volume=("tick_volume", "sum"),
                    spread=("spread", "max"),
                )
                .reset_index()
            )
        return normalise_candles(m5[(m5["time"] >= start) & (m5["time"] < end)])

    def tick(self, symbol: str) -> Tick:
        self._require()
        for spec, (_c, _d, mid, _tv) in zip(self.forex_symbols(), _MOCK_PAIRS):
            if spec.name == symbol:
                half = spec.spread_points * spec.point / 2
                return Tick(
                    symbol=symbol,
                    time=utc_now(),
                    bid=round(mid - half, spec.digits),
                    ask=round(mid + half, spec.digits),
                )
        raise MT5Error(f"Unknown symbol: {symbol}")
