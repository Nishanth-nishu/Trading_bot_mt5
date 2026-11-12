# API

Base URL `http://127.0.0.1:8010`. Interactive reference: `/docs`. All
timestamps are UTC. Only the endpoints below exist; the rest of spec
section 26 is not implemented.

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | Backend, database, adapter kind (`mt5_is_simulated`), connection, operating mode, kill-switch flag. `real_money_execution` is always `false`. |
| GET | `/api/system/state` | Operating mode, timeframes, history targets, risk defaults. |
| GET | `/api/mt5/status` | Adapter, connection, terminal name/build. |
| POST | `/api/mt5/connect` | Connect the configured adapter. Failure is returned in `error` with the MT5 code logged to `audit_logs`. |
| POST | `/api/mt5/disconnect` | Disconnect. |
| GET | `/api/mt5/account` | Balance, equity, margin, currency, leverage, demo verification, discrepancy against the requested 1,000 balance. Login is masked. `409` if not connected. |
| GET | `/api/mt5/symbols` | Forex symbols discovered from the broker with full specifications. `409` if not connected. |

| GET | `/api/data/datasets` | Cached datasets with source (`is_simulated`), coverage, 24/12-month flags, quality status, failures and warnings. |
| POST | `/api/data/update` | Body `{"symbol": "...", "timeframes": ["H1"]}` (timeframes optional; default all four). Downloads missing bars and re-validates. `409` if not connected. Runs synchronously. |
| GET | `/api/mt5/historical` | `?dataset_id=&limit=` (1–5000). Most recent cached candles. Reads the cache; it does not call the broker. |
| GET | `/api/data/features` | `?dataset_id=&limit=`. Most recent rows of the versioned feature set. |
| GET | `/api/indicators` | Indicator catalogue with inputs and default parameters. |

Not yet present: authentication, rate limiting, WebSockets.
