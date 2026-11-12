"""Environment-based configuration.

All values come from environment variables prefixed ``TRADELAB_`` or a local
``.env`` file. There is deliberately no setting that enables real-money
execution: the platform is demo-only and no such code path exists.
"""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class OperatingMode(StrEnum):
    """Internal operating modes. There is no live/real-money mode."""

    RESEARCH = "research"
    ASSISTED = "assisted"
    DEMO_AUTONOMOUS = "demo_autonomous"


class MT5AdapterKind(StrEnum):
    MOCK = "mock"
    REAL = "real"


class RiskDefaults(BaseSettings):
    """Initial engineering safeguards (spec section 12). Not claims of optimality."""

    model_config = SettingsConfigDict(env_prefix="TRADELAB_RISK_", extra="ignore")

    risk_per_trade_pct: float = Field(0.5, gt=0, le=2.0)
    max_daily_loss_pct: float = Field(2.0, gt=0, le=5.0)
    max_total_drawdown_pct: float = Field(5.0, gt=0, le=20.0)
    max_open_positions: int = Field(3, ge=1, le=10)
    max_trades_per_day: int = Field(10, ge=1, le=50)
    min_reward_to_risk: float = Field(1.5, ge=1.0, le=10.0)
    max_concurrent_planned_risk_pct: float = Field(1.5, gt=0, le=5.0)
    mandatory_stop_loss: bool = True


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="TRADELAB_",
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "TradeLab MT5"
    environment: str = "development"

    # API
    api_host: str = "127.0.0.1"
    api_port: int = 8010
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # Storage
    database_url: str = f"sqlite:///{(PROJECT_ROOT / 'storage' / 'tradelab.db').as_posix()}"
    data_dir: Path = PROJECT_ROOT / "data"
    export_dir: Path = PROJECT_ROOT / "exports"
    log_dir: Path = PROJECT_ROOT / "logs"

    # MT5. Broker not selected yet: everything broker-specific is optional.
    mt5_adapter: MT5AdapterKind = MT5AdapterKind.MOCK
    mt5_terminal_path: str | None = None
    mt5_login: int | None = None
    mt5_password: SecretStr | None = None
    mt5_server: str | None = None

    # Research configuration (spec section 2)
    requested_initial_balance: float = 1000.0
    timeframes: list[str] = ["M5", "M15", "H1", "H4"]
    history_target_months: int = 24
    history_minimum_months: int = 12
    demo_experiment_days: int = 30

    risk: RiskDefaults = Field(default_factory=RiskDefaults)


@lru_cache
def get_settings() -> Settings:
    return Settings()
