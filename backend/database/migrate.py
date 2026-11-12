"""Programmatic Alembic runner (used at startup and in tests)."""

from __future__ import annotations

from alembic import command
from alembic.config import Config

from backend.config.settings import PROJECT_ROOT


def alembic_config(database_url: str) -> Config:
    cfg = Config()
    cfg.set_main_option("script_location", str(PROJECT_ROOT / "migrations"))
    cfg.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    return cfg


def upgrade_to_head(database_url: str) -> None:
    command.upgrade(alembic_config(database_url), "head")
