# Development log

## 2026-11-12 — Phase 0: repository and foundation

### Environment

| Item | Finding |
|---|---|
| Operating system | Windows 11 Pro 10.0.26200 |
| Python | 3.11.9 (also 3.14 present; 3.11 used) |
| MT5 terminal | Not installed (no `terminal64.exe`, no MetaQuotes data folder) |
| MT5 Python package | Was absent; `MetaTrader5 5.0.6231` installed into `.venv` |
| Repository | Empty folder, not a git repository |
| Node / npm | 24.22.1 / 11.19.1 |
| Database | SQLite 3.45.1 available; PostgreSQL not installed |
| Docker | Not installed |
| Port 8000 | In use by another program; API moved to 8010 |

### Built

Project structure, settings, SQLite + Alembic migration, FastAPI app with
health / system / MT5 endpoints, connector interface with mock and real
adapters, demo guard, React dashboard (Overview, Settings), documentation.

### Evidence

- Backend: `pytest` — 26 passed (mock adapter; one test drives the real
  `MetaTrader5` package and confirms it fails cleanly with no terminal).
- Frontend: `npm run build` (type-check + bundle) succeeded; `npm test` — 1 passed.
- Manual: both servers started; dashboard loaded, Connect showed the mock
  account (1,000.00 EUR, demo verified, labelled simulated) and 8 suffixed
  symbols; no browser console errors.

### Gate

Phase 0 gate — backend, frontend, database and health checks work — **met**.

## 2026-11-12 — Phase 2: data and indicator engine (simulated data only)

Built out of order at the user's instruction; Phase 1 is still blocked on an
MT5 terminal.

### Built

Candle retrieval on both connectors, canonical candle frame, data validation,
Parquet cache with incremental updates and provenance, 15 indicators with a
registry, versioned feature set with lookahead-safe higher-timeframe
alignment, data API, Historical Data dashboard page.

### Evidence

- Backend: `pytest` — 101 passed (all on the mock adapter).
  - Indicators: RSI against a published 14-period worked example (within
    0.15, the example's own rounding); EMA, Wilder, RSI, ATR, ADX against
    independent naive-loop references; a truncation (no-lookahead) test for
    every registered indicator and for the feature set.
  - Validation: each defect type is detected; weekend gaps are not counted as
    missing; the 12-month fallback is a labelled warning; below 12 months fails.
  - History: first download meets the 24-month target, forming bars are not
    stored, incremental updates append without rewriting, all four timeframes.
- Frontend: build succeeded; 1 test passed.
- Manual: downloaded EURUSD.m in the dashboard — four datasets, 24.21 months
  each, all "ok", labelled Simulated.

### Defect found and fixed

The first dashboard download showed 6 one-bar gaps in M5. Cause: the mock
connector dropped the last bar of any request ending mid-bar and built
higher-timeframe bars from truncated data. The tests had only used
bar-aligned times. Fixed in `backend/mt5/mock.py`; two regression tests added.

### Gate

Phase 2 gate — validated historical datasets and indicators — **not met**:
indicators are validated, but no real dataset has been validated.

### Next

Phase 1 needs an MT5 terminal logged in to a demo account. Work that does not
need it (Phase 2 data validation and indicators against cached or mock data,
Phase 3 strategy framework) can proceed meanwhile.
