import inspect

import pytest
from pydantic import ValidationError

from backend.config.settings import MT5AdapterKind, OperatingMode, RiskDefaults, Settings
from backend.mt5.factory import build_connector
from backend.mt5.interface import MT5Connector, MT5Error, NotConnectedError
from backend.mt5.mock import MockMT5Connector
from backend.mt5.real import RealMT5Connector


def test_spec_defaults():
    s = Settings(_env_file=None)
    assert s.mt5_adapter is MT5AdapterKind.MOCK
    assert s.timeframes == ["M5", "M15", "H1", "H4"]
    assert s.requested_initial_balance == 1000.0
    assert (s.history_target_months, s.history_minimum_months) == (24, 12)
    assert s.api_host == "127.0.0.1"
    r = s.risk
    assert (r.risk_per_trade_pct, r.max_daily_loss_pct, r.max_total_drawdown_pct) == (0.5, 2.0, 5.0)
    assert (r.max_open_positions, r.max_trades_per_day) == (3, 10)
    assert (r.min_reward_to_risk, r.max_concurrent_planned_risk_pct) == (1.5, 1.5)
    assert r.mandatory_stop_loss is True


def test_risk_settings_are_bounded():
    with pytest.raises(ValidationError):
        RiskDefaults(risk_per_trade_pct=25)
    with pytest.raises(ValidationError):
        RiskDefaults(min_reward_to_risk=0.2)


def test_no_live_operating_mode_exists():
    assert {m.value for m in OperatingMode} == {"research", "assisted", "demo_autonomous"}


def test_connector_interface_has_no_order_methods_yet():
    names = {n for n, _ in inspect.getmembers(MT5Connector, inspect.isfunction)}
    assert not {n for n in names if "order" in n or "close" in n or "trade" in n}


def test_factory_is_explicit():
    assert isinstance(build_connector(Settings(_env_file=None)), MockMT5Connector)
    assert isinstance(
        build_connector(Settings(_env_file=None, mt5_adapter="real")), RealMT5Connector
    )


def test_mock_requires_connection():
    c = MockMT5Connector()
    with pytest.raises(NotConnectedError):
        c.account_info()


def test_mock_symbols_are_suffixed_and_consistent():
    c = MockMT5Connector(symbol_suffix=".x")
    c.connect()
    specs = c.forex_symbols()
    assert specs
    for s in specs:
        assert s.name == s.canonical + ".x"
        assert s.canonical == s.currency_base + s.currency_profit
        assert s.volume_min <= s.volume_max and s.volume_step > 0
        tick = c.tick(s.name)
        assert tick.ask > tick.bid
        assert tick.time.tzinfo is not None
    with pytest.raises(MT5Error):
        c.tick("EURUSD")  # bare name does not exist at this mock broker


def test_real_connector_without_terminal_fails_cleanly():
    """No MT5 terminal on the dev machine: connect must raise MT5Error, not crash."""
    c = RealMT5Connector(terminal_path=r"C:\nonexistent\terminal64.exe")
    with pytest.raises(MT5Error):
        c.connect()
    assert not c.is_connected()
