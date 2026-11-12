"""FastAPI application factory."""

from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import asdict

from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from backend import __version__
from backend.api import schemas
from backend.api.data_routes import build_data_router
from backend.data.history import HistoryManager
from backend.config.settings import Settings, get_settings
from backend.core.system_state import audit, get_state, reset_on_startup
from backend.core.timeutil import utc_now
from backend.database.migrate import upgrade_to_head
from backend.database.session import database_is_reachable, make_engine, make_session_factory
from backend.mt5.demo_guard import assess_account
from backend.mt5.factory import build_connector
from backend.mt5.interface import MT5Connector, MT5Error, NotConnectedError


def _mask_login(login: int) -> str:
    text = str(login)
    return "*" * max(len(text) - 3, 0) + text[-3:]


def create_app(settings: Settings | None = None, connector: MT5Connector | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        upgrade_to_head(settings.database_url)
        engine = make_engine(settings.database_url)
        app.state.engine = engine
        app.state.sessions = make_session_factory(engine)
        app.state.connector = connector or build_connector(settings)
        app.state.history = HistoryManager(
            app.state.connector,
            app.state.sessions,
            settings.data_dir,
            target_months=settings.history_target_months,
            minimum_months=settings.history_minimum_months,
        )
        with app.state.sessions() as session:
            reset_on_startup(session)
            audit(session, "system", "startup", f"adapter={app.state.connector.kind}")
            session.commit()
        try:
            yield
        finally:
            try:
                app.state.connector.disconnect()
            finally:
                engine.dispose()

    app = FastAPI(title=settings.app_name, version=__version__, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    api = APIRouter(prefix="/api")

    def conn(request: Request) -> MT5Connector:
        return request.app.state.connector

    def connected(request: Request) -> MT5Connector:
        c = conn(request)
        if not c.is_connected():
            raise HTTPException(status_code=409, detail="MT5 is not connected.")
        return c

    def log(request: Request, category: str, event: str, detail: str | None = None) -> None:
        with request.app.state.sessions() as session:
            audit(session, category, event, detail)
            session.commit()

    @api.get("/health", response_model=schemas.HealthResponse, tags=["system"])
    def health(request: Request):
        db_ok = database_is_reachable(request.app.state.engine)
        mode, kill = "unknown", True  # fail closed if state cannot be read
        if db_ok:
            with request.app.state.sessions() as session:
                state = get_state(session)
                mode, kill = state.operating_mode, state.kill_switch_engaged
                session.commit()
        c = conn(request)
        return schemas.HealthResponse(
            status="ok" if db_ok else "degraded",
            app=settings.app_name,
            version=__version__,
            environment=settings.environment,
            server_time_utc=utc_now(),
            database_ok=db_ok,
            mt5_adapter=c.kind,
            mt5_is_simulated=c.kind != "real",
            mt5_connected=c.is_connected(),
            operating_mode=mode,
            kill_switch_engaged=kill,
            real_money_execution=False,
        )

    @api.get("/system/state", response_model=schemas.SystemStateResponse, tags=["system"])
    def system_state(request: Request):
        with request.app.state.sessions() as session:
            state = get_state(session)
            session.commit()
            return schemas.SystemStateResponse(
                operating_mode=state.operating_mode,
                kill_switch_engaged=state.kill_switch_engaged,
                demo_only=True,
                timeframes=settings.timeframes,
                history_target_months=settings.history_target_months,
                history_minimum_months=settings.history_minimum_months,
                demo_experiment_days=settings.demo_experiment_days,
                risk=schemas.RiskSettingsOut(**settings.risk.model_dump()),
            )

    def _status(c: MT5Connector, error: str | None = None) -> schemas.MT5StatusResponse:
        is_connected = c.is_connected()
        name, build = None, None
        if is_connected:
            try:
                info = c.terminal_info()
                name, build = info.name, info.build
            except MT5Error as exc:
                error = str(exc)
        return schemas.MT5StatusResponse(
            adapter=c.kind,
            is_simulated=c.kind != "real",
            connected=is_connected,
            terminal_name=name,
            terminal_build=build,
            error=error,
        )

    @api.get("/mt5/status", response_model=schemas.MT5StatusResponse, tags=["mt5"])
    def mt5_status(request: Request):
        return _status(conn(request))

    @api.post("/mt5/connect", response_model=schemas.MT5StatusResponse, tags=["mt5"])
    def mt5_connect(request: Request):
        c = conn(request)
        try:
            c.connect()
        except MT5Error as exc:
            log(request, "mt5", "connect_failed", f"code={exc.code} {exc}")
            return _status(c, error=str(exc))
        log(request, "mt5", "connected", f"adapter={c.kind}")
        return _status(c)

    @api.post("/mt5/disconnect", response_model=schemas.MT5StatusResponse, tags=["mt5"])
    def mt5_disconnect(request: Request):
        c = conn(request)
        c.disconnect()
        log(request, "mt5", "disconnected", f"adapter={c.kind}")
        return _status(c)

    @api.get("/mt5/account", response_model=schemas.AccountResponse, tags=["mt5"])
    def mt5_account(request: Request):
        c = connected(request)
        try:
            account = c.account_info()
        except NotConnectedError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except MT5Error as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        verification = assess_account(account, settings.mt5_login)
        requested = settings.requested_initial_balance
        discrepancy = round(account.balance - requested, 2)
        return schemas.AccountResponse(
            is_simulated=c.kind != "real",
            login_masked=_mask_login(account.login),
            server=account.server,
            company=account.company,
            currency=account.currency,
            leverage=account.leverage,
            balance=account.balance,
            equity=account.equity,
            margin=account.margin,
            margin_free=account.margin_free,
            margin_level=account.margin_level,
            trade_mode=account.trade_mode.value,
            demo_verification=schemas.DemoVerificationOut(**asdict(verification)),
            requested_initial_balance=requested,
            balance_discrepancy=discrepancy,
            balance_matches_request=abs(discrepancy) < 0.005,
        )

    @api.get("/mt5/symbols", response_model=schemas.SymbolsResponse, tags=["mt5"])
    def mt5_symbols(request: Request):
        c = connected(request)
        try:
            specs = c.forex_symbols()
        except MT5Error as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        out = [schemas.SymbolOut.model_validate(asdict(s)) for s in specs]
        return schemas.SymbolsResponse(is_simulated=c.kind != "real", count=len(out), symbols=out)

    app.include_router(api)
    app.include_router(build_data_router(settings))
    return app
