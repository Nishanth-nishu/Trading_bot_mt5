"""API response schemas. Nothing here may carry credentials."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str  # "ok" | "degraded"
    app: str
    version: str
    environment: str
    server_time_utc: datetime
    database_ok: bool
    mt5_adapter: str  # "mock" | "real"
    mt5_is_simulated: bool
    mt5_connected: bool
    operating_mode: str
    kill_switch_engaged: bool
    real_money_execution: bool  # always False; no such code path exists


class MT5StatusResponse(BaseModel):
    adapter: str
    is_simulated: bool
    connected: bool
    terminal_name: str | None = None
    terminal_build: int | None = None
    error: str | None = None


class DemoVerificationOut(BaseModel):
    is_demo: bool
    reason: str


class AccountResponse(BaseModel):
    is_simulated: bool
    login_masked: str
    server: str
    company: str
    currency: str
    leverage: int
    balance: float
    equity: float
    margin: float
    margin_free: float
    margin_level: float | None
    trade_mode: str
    demo_verification: DemoVerificationOut
    requested_initial_balance: float
    balance_discrepancy: float  # actual - requested
    balance_matches_request: bool


class SymbolOut(BaseModel):
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


class SymbolsResponse(BaseModel):
    is_simulated: bool
    count: int
    symbols: list[SymbolOut]


class RiskSettingsOut(BaseModel):
    risk_per_trade_pct: float
    max_daily_loss_pct: float
    max_total_drawdown_pct: float
    max_open_positions: int
    max_trades_per_day: int
    min_reward_to_risk: float
    max_concurrent_planned_risk_pct: float
    mandatory_stop_loss: bool


class SystemStateResponse(BaseModel):
    operating_mode: str
    kill_switch_engaged: bool
    demo_only: bool
    timeframes: list[str]
    history_target_months: int
    history_minimum_months: int
    demo_experiment_days: int
    risk: RiskSettingsOut
