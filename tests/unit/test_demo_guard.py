import pytest

from backend.mt5.demo_guard import (
    DemoAccountRequired,
    assess_account,
    require_demo,
    verify_connector,
)
from backend.mt5.interface import AccountTradeMode
from backend.mt5.mock import MockMT5Connector


def _account(mode):
    c = MockMT5Connector(trade_mode=mode)
    c.connect()
    return c.account_info()


def test_demo_account_is_accepted():
    assert assess_account(_account(AccountTradeMode.DEMO)).is_demo


@pytest.mark.parametrize(
    "mode", [AccountTradeMode.REAL, AccountTradeMode.CONTEST, AccountTradeMode.UNKNOWN]
)
def test_non_demo_accounts_are_rejected(mode):
    result = assess_account(_account(mode))
    assert not result.is_demo
    assert result.reason


def test_missing_account_is_rejected():
    assert not assess_account(None).is_demo


def test_unrecognised_classification_is_rejected():
    from dataclasses import replace

    account = replace(_account(AccountTradeMode.DEMO), trade_mode="demo")  # raw str, not enum
    assert not assess_account(account).is_demo


def test_wrong_account_identity_is_rejected():
    account = _account(AccountTradeMode.DEMO)
    assert not assess_account(account, expected_login=account.login + 1).is_demo
    assert assess_account(account, expected_login=account.login).is_demo


def test_unverifiable_connector_fails_closed():
    disconnected = MockMT5Connector()
    assert not verify_connector(disconnected).is_demo
    with pytest.raises(DemoAccountRequired):
        require_demo(disconnected)


def test_require_demo_rejects_real_account():
    c = MockMT5Connector(trade_mode=AccountTradeMode.REAL)
    c.connect()
    with pytest.raises(DemoAccountRequired):
        require_demo(c)
