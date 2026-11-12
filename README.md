# TradeLab MT5

Multi-strategy quantitative forex research, backtesting and **demo-only** MT5
trading platform. There is no real-money execution path in this codebase.

**Current state: Phase 0 (foundation) complete; Phase 2 (data and indicators)
built and tested on simulated data only.** Phase 1 and the Phase 2 gate both
need a real MT5 demo terminal and remain open. No strategies, backtesting,
risk engine or order execution exist yet. See
[docs/development-log.md](docs/development-log.md) for what is built and
[docs/known-limitations.md](docs/known-limitations.md) for what is not.

## Run

Requires Windows, Python 3.11 and Node 20+.

```
py -3.11 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.lock
.venv\Scripts\python -m pip install -e ".[dev,mt5]" --no-deps
.venv\Scripts\python -m backend.main          # API on http://127.0.0.1:8010
```

```
cd frontend
npm install
npm run dev                                   # dashboard on http://127.0.0.1:5173
```

The database (SQLite, `storage/tradelab.db`) is created and migrated on startup.

## MT5 adapters

| `TRADELAB_MT5_ADAPTER` | Source | Notes |
|---|---|---|
| `mock` (default) | Simulated | Every API response and the dashboard label it as simulated. |
| `real` | Official `MetaTrader5` package + installed terminal | Not yet verified against a terminal (Phase 1 gate). |

There is no automatic fallback between the two. Copy `.env.example` to `.env`
to configure.

## Test

```
.venv\Scripts\python -m pytest        # backend (mock adapter)
cd frontend && npm test && npm run build
```

## Documents

- [Architecture](docs/architecture.md)
- [API](docs/api.md) (live reference at `/docs` when the backend runs)
- [Decision register](docs/decision-register.md)
- [Known limitations](docs/known-limitations.md)
- [Development log](docs/development-log.md)
