"""Connector selection. Explicit only: there is no automatic fallback
between adapters, so a mock can never silently stand in for a broker."""

from __future__ import annotations

from backend.config.settings import MT5AdapterKind, Settings
from backend.mt5.interface import MT5Connector
from backend.mt5.mock import MockMT5Connector
from backend.mt5.real import RealMT5Connector


def build_connector(settings: Settings) -> MT5Connector:
    if settings.mt5_adapter is MT5AdapterKind.REAL:
        return RealMT5Connector(
            terminal_path=settings.mt5_terminal_path,
            login=settings.mt5_login,
            password=settings.mt5_password.get_secret_value() if settings.mt5_password else None,
            server=settings.mt5_server,
        )
    return MockMT5Connector(balance=settings.requested_initial_balance)
