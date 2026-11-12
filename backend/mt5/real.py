"""Real MT5 connector using the official ``MetaTrader5`` package.

Windows only; needs an installed MT5 terminal. The package is imported
lazily so the rest of the application runs without it.

STATUS: written against the documented MetaTrader5 Python API but NOT yet
exercised against a terminal (none is installed on the development machine).
Verifying it is the Phase 1 gate.
"""

from __future__ import annotations

import threading
from datetime import UTC, datetime
from typing import Any

from backend.mt5.interface import (
    AccountInfo,
    AccountTradeMode,
    MT5Connector,
    MT5Error,
    NotConnectedError,
    SymbolSpec,
    TerminalInfo,
    Tick,
)


def _load_mt5() -> Any:
    try:
        import MetaTrader5 as mt5  # noqa: N813
    except ImportError as exc:
        raise MT5Error(
            "The MetaTrader5 Python package is not installed (pip install -e .[mt5])."
        ) from exc
    return mt5


class RealMT5Connector(MT5Connector):
    kind = "real"
    time_basis = "broker_server_time_unconverted"

    def __init__(
        self,
        *,
        terminal_path: str | None = None,
        login: int | None = None,
        password: str | None = None,
        server: str | None = None,
    ):
        self._terminal_path = terminal_path
        self._login = login
        self._password = password
        self._server = server
        self._mt5: Any = None
        self._connected = False
        # The MetaTrader5 module is a process-wide singleton and not thread-safe.
        self._lock = threading.RLock()

    def _fail(self, what: str) -> MT5Error:
        code, message = (None, "unknown error")
        try:
            code, message = self._mt5.last_error()
        except Exception:
            pass
        return MT5Error(f"{what}: {message}", code=code)

    def connect(self) -> None:
        with self._lock:
            self._mt5 = _load_mt5()
            kwargs: dict[str, Any] = {}
            if self._terminal_path:
                kwargs["path"] = self._terminal_path
            if self._login is not None:
                kwargs["login"] = self._login
            if self._password:
                kwargs["password"] = self._password
            if self._server:
                kwargs["server"] = self._server
            if not self._mt5.initialize(**kwargs):
                self._connected = False
                raise self._fail("MT5 initialize failed")
            self._connected = True

    def disconnect(self) -> None:
        with self._lock:
            if self._mt5 is not None:
                self._mt5.shutdown()
            self._connected = False

    def is_connected(self) -> bool:
        with self._lock:
            if not self._connected or self._mt5 is None:
                return False
            info = self._mt5.terminal_info()
            return bool(info is not None and info.connected)

    def _require(self) -> None:
        if not self._connected or self._mt5 is None:
            raise NotConnectedError("MT5 terminal is not connected.")

    def terminal_info(self) -> TerminalInfo:
        with self._lock:
            self._require()
            info = self._mt5.terminal_info()
            if info is None:
                raise self._fail("terminal_info failed")
            return TerminalInfo(
                name=info.name,
                company=info.company,
                build=info.build,
                connected=bool(info.connected),
                trade_allowed=bool(info.trade_allowed),
            )

    def _trade_mode(self, raw: int) -> AccountTradeMode:
        mt5 = self._mt5
        mapping = {
            getattr(mt5, "ACCOUNT_TRADE_MODE_DEMO", object()): AccountTradeMode.DEMO,
            getattr(mt5, "ACCOUNT_TRADE_MODE_CONTEST", object()): AccountTradeMode.CONTEST,
            getattr(mt5, "ACCOUNT_TRADE_MODE_REAL", object()): AccountTradeMode.REAL,
        }
        return mapping.get(raw, AccountTradeMode.UNKNOWN)

    def account_info(self) -> AccountInfo:
        with self._lock:
            self._require()
            info = self._mt5.account_info()
            if info is None:
                raise self._fail("account_info failed")
            return AccountInfo(
                login=int(info.login),
                server=info.server,
                company=info.company,
                currency=info.currency,
                leverage=int(info.leverage),
                balance=float(info.balance),
                equity=float(info.equity),
                margin=float(info.margin),
                margin_free=float(info.margin_free),
                margin_level=float(info.margin_level) if info.margin else None,
                trade_mode=self._trade_mode(info.trade_mode),
            )

    def forex_symbols(self) -> list[SymbolSpec]:
        with self._lock:
            self._require()
            mt5 = self._mt5
            symbols = mt5.symbols_get()
            if symbols is None:
                raise self._fail("symbols_get failed")
            forex_modes = {
                getattr(mt5, "SYMBOL_CALC_MODE_FOREX", None),
                getattr(mt5, "SYMBOL_CALC_MODE_FOREX_NO_LEVERAGE", None),
            } - {None}
            disabled = getattr(mt5, "SYMBOL_TRADE_MODE_DISABLED", 0)
            specs = []
            for s in symbols:
                if s.trade_calc_mode not in forex_modes:
                    continue
                specs.append(
                    SymbolSpec(
                        name=s.name,
                        canonical=f"{s.currency_base}{s.currency_profit}",
                        currency_base=s.currency_base,
                        currency_profit=s.currency_profit,
                        currency_margin=s.currency_margin,
                        digits=int(s.digits),
                        point=float(s.point),
                        tick_size=float(s.trade_tick_size),
                        tick_value=float(s.trade_tick_value),
                        contract_size=float(s.trade_contract_size),
                        volume_min=float(s.volume_min),
                        volume_max=float(s.volume_max),
                        volume_step=float(s.volume_step),
                        spread_points=int(s.spread),
                        trade_allowed=s.trade_mode != disabled,
                        path=s.path,
                    )
                )
            return specs

    def rates(self, symbol: str, timeframe: str, start: datetime, end: datetime):
        import pandas as pd

        from backend.data.candles import empty_candles, normalise_candles

        with self._lock:
            self._require()
            mt5 = self._mt5
            constant = getattr(mt5, f"TIMEFRAME_{timeframe}", None)
            if constant is None:
                raise MT5Error(f"Unsupported timeframe: {timeframe}")
            if not mt5.symbol_select(symbol, True):
                raise self._fail(f"symbol_select({symbol}) failed")
            raw = mt5.copy_rates_range(symbol, constant, start, end)
            if raw is None:
                raise self._fail(f"copy_rates_range({symbol}, {timeframe}) failed")
        if len(raw) == 0:
            return empty_candles()
        frame = pd.DataFrame(raw)
        # Bar times arrive as broker-server wall-clock seconds, labelled here as
        # UTC without conversion. See ``time_basis``; conversion is Phase 1 work.
        frame["time"] = pd.to_datetime(frame["time"], unit="s", utc=True)
        frame = normalise_candles(frame)
        return frame[frame["time"] < pd.Timestamp(end)].reset_index(drop=True)

    def tick(self, symbol: str) -> Tick:
        with self._lock:
            self._require()
            t = self._mt5.symbol_info_tick(symbol)
            if t is None:
                raise self._fail(f"symbol_info_tick({symbol}) failed")
            # NOTE: MT5 tick times are in broker server time expressed as an
            # epoch. The server-time -> UTC offset policy is defined in Phase 1.
            return Tick(
                symbol=symbol,
                time=datetime.fromtimestamp(t.time, tz=UTC),
                bid=float(t.bid),
                ask=float(t.ask),
            )
