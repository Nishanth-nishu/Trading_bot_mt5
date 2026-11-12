"""Demo-account enforcement. Fails closed.

An account is tradable only when the broker positively classifies it as
DEMO. Real, contest, unknown or unreadable accounts are all rejected; there
is no override flag.
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.mt5.interface import AccountInfo, AccountTradeMode, MT5Connector


class DemoAccountRequired(Exception):
    pass


@dataclass(frozen=True)
class DemoVerification:
    is_demo: bool
    reason: str


def assess_account(account: AccountInfo | None, expected_login: int | None = None) -> DemoVerification:
    if account is None:
        return DemoVerification(False, "Account information could not be read.")
    if not isinstance(account.trade_mode, AccountTradeMode):
        return DemoVerification(False, "Account classification is not recognised.")
    if account.trade_mode is not AccountTradeMode.DEMO:
        return DemoVerification(
            False, f"Account is classified '{account.trade_mode.value}', not demo."
        )
    if expected_login is not None and account.login != expected_login:
        return DemoVerification(False, "Connected account does not match the configured account.")
    return DemoVerification(True, "Broker classifies this account as demo.")


def verify_connector(connector: MT5Connector, expected_login: int | None = None) -> DemoVerification:
    """Read the account fresh from the connector and assess it."""
    try:
        account = connector.account_info()
    except Exception as exc:  # any failure to verify is a rejection
        return DemoVerification(False, f"Account verification failed: {type(exc).__name__}.")
    return assess_account(account, expected_login)


def require_demo(connector: MT5Connector, expected_login: int | None = None) -> None:
    result = verify_connector(connector, expected_login)
    if not result.is_demo:
        raise DemoAccountRequired(result.reason)
