# Architecture

Describes what exists today. Planned modules are listed only as placeholders.

## Processes

```
Browser (React, :5173) --/api proxy--> FastAPI backend (:8010, localhost only)
                                         |-- SQLite (storage/tradelab.db, Alembic-migrated)
                                         `-- MT5Connector --> MockMT5Connector (simulated)
                                                          `-> RealMT5Connector --> MT5 terminal
```

The frontend never talks to MT5. `backend/mt5/` is the only package that may
import `MetaTrader5`; everything else depends on `backend/mt5/interface.py`.

## Implemented (Phase 0)

| Path | Responsibility |
|---|---|
| `backend/config/settings.py` | `TRADELAB_*` environment settings, bounded risk defaults, operating modes (research / assisted / demo_autonomous; no live mode). |
| `backend/database/` | Models (`system_state`, `audit_logs`, `historical_data_metadata`), engine/session factory, programmatic Alembic upgrade. |
| `backend/core/system_state.py` | Persisted operating state; forces research mode on every startup; audit helper. |
| `backend/mt5/interface.py` | Read-only connector contract and broker-neutral dataclasses. No order methods yet. |
| `backend/mt5/mock.py` | Simulated connector (EUR account, suffixed symbols). |
| `backend/mt5/real.py` | Official-package connector: connect, terminal, account, forex symbol discovery, tick. |
| `backend/mt5/demo_guard.py` | Fail-closed demo-account verification. |
| `backend/mt5/factory.py` | Explicit adapter selection; no fallback. |
| `backend/api/` | FastAPI app factory, schemas, endpoints (see api.md). |
| `frontend/` | React + TypeScript + Vite + Tailwind + TanStack Query + Zustand. Overview and Settings pages. |

## Implemented (Phase 2)

| Path | Responsibility |
|---|---|
| `backend/data/candles.py` | Canonical candle frame: bar-open `time` in UTC, OHLC, tick volume, spread. Naive timestamps rejected. |
| `backend/data/timeframes.py` | M5, M15, H1, H4. |
| `backend/data/quality.py` | Validation: duplicates, ordering, grid alignment, OHLC validity, weekend vs unexpected gaps, outliers, spread availability, 24/12-month coverage. Reports only; never repairs or fills. |
| `backend/data/history.py` | Chunked download through the connector, Parquet cache per source (`data/history/<kind>__<server>/<symbol>/<TF>.parquet`), incremental update, closed bars only, atomic writes, provenance in `historical_data_metadata`. Refuses to serve datasets that failed validation. |
| `backend/indicators/core.py` | SMA, EMA, RSI, MACD, ATR, ADX/DI, Bollinger, stochastic, ROC, Donchian, Keltner, Supertrend, Ichimoku, z-score, rolling volatility. Own implementations; conventions documented in the module. |
| `backend/indicators/registry.py` | Catalogue and uniform `compute()` with parameter validation. |
| `backend/features/engine.py` | Versioned feature set (ATR-normalised trend, volatility, displacement, breakout, spread features) and `align_higher_timeframe`, which only ever attaches higher-timeframe bars that have already closed. |
| `backend/api/data_routes.py` | Data, indicator and feature endpoints. |
| `frontend/src/pages/Data.tsx` | Download/update history and inspect coverage and quality. |

**Timestamp convention:** a row's `time` is the bar open. Everything computed
on a row is known at `time + timeframe`, which is the decision timestamp.

## Safety properties already enforced

- No indicator or feature value depends on later bars (truncation tests over the whole registry and feature set).

- No order-submission method exists on the connector interface (tested).
- Demo verification rejects real, contest, unknown and unreadable accounts (tested).
- A restart always returns to research mode and never clears the kill-switch flag (tested).
- API binds to 127.0.0.1; CORS limited to the dashboard origin; account login is masked; passwords never leave settings.

## Placeholders

Every other package under `backend/` and `strategy_library/` contains only a
docstring naming the phase that will implement it.
