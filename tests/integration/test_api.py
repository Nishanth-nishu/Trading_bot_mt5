"""API tests against the MOCK adapter."""

from fastapi.testclient import TestClient
from sqlalchemy import inspect, select

from backend.api.app import create_app
from backend.database.models import AuditLog, Base, SystemState
from backend.mt5.interface import AccountTradeMode
from backend.mt5.mock import MockMT5Connector


def test_health(client):
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert body["database_ok"] is True
    assert body["mt5_adapter"] == "mock" and body["mt5_is_simulated"] is True
    assert body["mt5_connected"] is False
    assert body["operating_mode"] == "research"
    assert body["real_money_execution"] is False
    assert body["server_time_utc"].endswith(("Z", "+00:00"))


def test_migrations_match_models(client):
    tables = set(inspect(client.app.state.engine).get_table_names())
    assert set(Base.metadata.tables) <= tables


def test_account_requires_connection(client):
    assert client.get("/api/mt5/account").status_code == 409
    assert client.get("/api/mt5/symbols").status_code == 409


def test_connect_account_symbols_disconnect(client):
    status = client.post("/api/mt5/connect").json()
    assert status["connected"] is True and status["is_simulated"] is True

    account = client.get("/api/mt5/account").json()
    assert account["currency"] == "EUR"  # read from the adapter, not assumed
    assert account["demo_verification"]["is_demo"] is True
    assert account["balance_matches_request"] is True
    assert "login" not in account and account["login_masked"].startswith("*")
    assert "password" not in str(account).lower()

    symbols = client.get("/api/mt5/symbols").json()
    assert symbols["count"] == len(symbols["symbols"]) > 0
    assert all(s["name"] != s["canonical"] for s in symbols["symbols"])

    assert client.post("/api/mt5/disconnect").json()["connected"] is False

    with client.app.state.sessions() as session:
        events = [r.event for r in session.scalars(select(AuditLog).order_by(AuditLog.id))]
    assert events == ["startup", "connected", "disconnected"]


def test_balance_discrepancy_is_reported(settings):
    connector = MockMT5Connector(balance=10_000.0)
    with TestClient(create_app(settings, connector)) as c:
        c.post("/api/mt5/connect")
        account = c.get("/api/mt5/account").json()
    assert account["balance_matches_request"] is False
    assert account["balance_discrepancy"] == 9000.0


def test_real_account_is_flagged_not_demo(settings):
    connector = MockMT5Connector(trade_mode=AccountTradeMode.REAL)
    with TestClient(create_app(settings, connector)) as c:
        c.post("/api/mt5/connect")
        account = c.get("/api/mt5/account").json()
    assert account["demo_verification"]["is_demo"] is False


def test_system_state_exposes_risk_defaults(client):
    body = client.get("/api/system/state").json()
    assert body["demo_only"] is True
    assert body["risk"]["risk_per_trade_pct"] == 0.5
    assert body["timeframes"] == ["M5", "M15", "H1", "H4"]


def test_restart_never_resumes_autonomous_mode(settings):
    with TestClient(create_app(settings, MockMT5Connector())) as c:
        with c.app.state.sessions() as session:
            state = session.get(SystemState, 1)
            state.operating_mode = "demo_autonomous"
            state.kill_switch_engaged = True
            session.commit()
    with TestClient(create_app(settings, MockMT5Connector())) as c:
        body = c.get("/api/health").json()
    assert body["operating_mode"] == "research"
    assert body["kill_switch_engaged"] is True  # a restart must not clear the kill switch


def test_cors_rejects_unknown_origin(client):
    r = client.get("/api/health", headers={"Origin": "http://evil.example"})
    assert "access-control-allow-origin" not in r.headers
