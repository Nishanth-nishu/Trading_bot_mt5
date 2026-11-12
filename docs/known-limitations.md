# Known limitations

Updated 2026-11-12 (Phase 0 complete; Phase 2 built on simulated data).

## Blockers for later phases

- **No MT5 terminal is installed** on the development machine and no broker is
  selected. `RealMT5Connector` has only been exercised to the point of failing
  cleanly without a terminal. The Phase 1 gate (real demo account data) cannot
  be passed until a terminal is installed and logged in to a demo account.

- **Phase 2 has only run on simulated candles.** The mock series is a seeded
  random walk: it has no edge, no real gaps, no spread dynamics. It proves the
  pipeline, nothing about markets. The Phase 2 gate ("validated historical
  datasets") is not met until real broker data passes validation.

## Phase 2 caveats

- `RealMT5Connector.rates` is untested against a terminal. It labels broker
  server time as UTC without converting it; such datasets carry a warning and
  session logic on them would be wrong. The conversion policy (including
  daylight saving) is Phase 1 work.
- Tick data is not downloaded or validated.
- Gap detection knows only the weekend close. Holidays and brokers' daily
  maintenance breaks will be reported as unexpected gaps on real data.
- Outlier detection is a simple multiple-of-median rule; it flags, it does
  not judge.
- Downloads run synchronously inside the HTTP request; a real 24-month M5
  download for many symbols needs a background job.
- Indicator warm-up values can differ slightly from MT5's built-in indicators
  because seeding conventions differ (see decision D14).
- The feature set covers spec section 7 except higher-timeframe alignment as
  a built-in column (the alignment function exists; wiring it per strategy is
  Phase 3/4).
- The dashboard cannot yet chart candles or indicators (Phase 8).

## Not implemented

- Everything in Phases 3–11: strategies, regimes, backtesting, optimisation,
  validation, portfolio engine, risk engine, execution, experiments,
  attribution, CSV export.
- Ten of the thirteen dashboard pages (they say so in the UI).
- Authentication, rate limiting, WebSockets, database backups.
- Credential storage in the OS keyring: the MT5 password is read from the
  environment / `.env` only.
- Settings and risk limits are read-only in the dashboard.
- 27 of the 30 database entities in the spec.
- Kill switch: only the persisted flag exists; nothing engages or acts on it yet.

## Caveats in what exists

- The mock adapter's prices, tick values and account are illustrative constants,
  not market data.
- MT5 tick timestamps are treated as UTC; the broker-server-time policy is a
  Phase 1 task.
- PostgreSQL is supported by design (SQLAlchemy + Alembic) but untested.
- The API is unauthenticated and therefore binds to localhost only. Do not
  expose it on a network.
- Frontend tests cover only time formatting; there are no component or e2e tests.
- Docker is not installed; no container files have been written.
