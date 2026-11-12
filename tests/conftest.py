"""Shared fixtures. Everything here uses the MOCK MT5 adapter and a
throwaway SQLite file; no test in this suite talks to a real terminal
unless marked ``real_mt5``."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.config.settings import Settings
from backend.mt5.mock import MockMT5Connector


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(
        _env_file=None,
        database_url=f"sqlite:///{(tmp_path / 'test.db').as_posix()}",
        mt5_adapter="mock",
        data_dir=tmp_path / "data",
    )


@pytest.fixture
def connector() -> MockMT5Connector:
    return MockMT5Connector()


@pytest.fixture
def client(settings, connector):
    with TestClient(create_app(settings, connector)) as c:
        yield c
