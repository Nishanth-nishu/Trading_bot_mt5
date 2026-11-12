"""Entry point: ``python -m backend.main`` (binds to localhost only by default)."""

from __future__ import annotations

import uvicorn

from backend.api.app import create_app
from backend.config.settings import get_settings

app = create_app()

if __name__ == "__main__":
    settings = get_settings()
    uvicorn.run(app, host=settings.api_host, port=settings.api_port)
