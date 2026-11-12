# Decision register

| # | Date | Decision | Reason |
|---|---|---|---|
| D1 | 2026-11-12 | Repository root is the working folder itself, not a nested `tradelab-mt5/`. | Avoids a redundant directory level. |
| D2 | 2026-11-12 | Python 3.11 in a project `.venv`; versions pinned in `requirements.lock`. | 3.11 is installed and supported by the MetaTrader5 package; keeps the global interpreter untouched. |
| D3 | 2026-11-12 | Adapter choice is explicit (`TRADELAB_MT5_ADAPTER`), default `mock`, with no automatic fallback. | A mock must never silently stand in for a broker, and vice versa. |
| D4 | 2026-11-12 | The connector interface is read-only until Phase 9. | No order path can exist before the risk engine and demo guard that must sit in front of it. |
| D5 | 2026-11-12 | Demo verification accepts only a positive DEMO classification; contest accounts are rejected too. | Fail closed; the spec permits demo only. |
| D6 | 2026-11-12 | Every startup resets the operating mode to research; the kill-switch flag persists. | Never resume trading silently; never clear a safety stop by restarting. |
| D7 | 2026-11-12 | Mock account currency is EUR and mock symbols carry a `.m` suffix. | Surfaces USD and bare-symbol assumptions early. |
| D8 | 2026-11-12 | Database tables are added in the phase that first uses them, each with a migration. | Avoids 30 untested, speculative tables; schema follows working code. |
| D9 | 2026-11-12 | Only dependencies in use are installed (pandas, scipy, etc. arrive in Phase 2). | Smaller, pinned surface. |
| D10 | 2026-11-12 | API default port is 8010. | Port 8000 is occupied by another program on the development machine. |
| D11 | 2026-11-12 | Backend exchanges UTC only; the dashboard shows UTC and IST, both labelled. | Spec requires UTC internally and a clearly identified display timezone. |
| D13 | 2026-11-12 | Indicators are implemented in-house, not with TA-Lib. | TA-Lib needs a C build on Windows; the spec allows independently validated implementations. Validated against a published RSI example, naive loop references and truncation tests. |
| D14 | 2026-11-12 | EMA and Wilder smoothing are SMA-seeded; first true range is high − low; Bollinger/z-score use population std. | Platforms differ; one stated convention keeps results reproducible. Values can differ slightly from MT5's own indicators during warm-up. |
| D15 | 2026-11-12 | Validation reports and never repairs; failed datasets are refused to consumers. | Spec: do not fill missing data with invented prices. |
| D16 | 2026-11-12 | Only closed bars are cached. | A forming bar would change after storage and leak into signals. |
| D17 | 2026-11-12 | Datasets are keyed by adapter kind and broker server. | Simulated candles can never mix with broker candles; different brokers' feeds stay separate. |
| D18 | 2026-11-12 | Ichimoku exposes a causal cloud and omits the chikou span. | The chikou span places a later close on an earlier bar. |
| D19 | 2026-11-12 | A "Historical Data" dashboard page was added beyond the twelve in the spec. | Data download and quality must be operable without code. |
| D20 | 2026-11-12 | Phase 2 was built before the Phase 1 gate, at the user's instruction. | No MT5 terminal is available yet. Both gates stay open until real data is validated. |
| D12 | 2026-11-12 | Migrations run automatically at backend startup. | Single-user local app; removes a manual step. Revisit for PostgreSQL deployments. |
