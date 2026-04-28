# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [1.8.0] - 2026-04-28 - Postgres

### Added

**omninance-backend:**

- `src/db.py` — full async rewrite using SQLModel + SQLAlchemy async engine (`asyncpg`); three ORM models replacing raw SQL:
  - `Strategy` — maps the existing strategy table; UUID primary key
  - `StrategyDailyLog` — tracks daily equity/PnL/holdings; `execute_at` and `compute_at` stored as timezone-aware `DateTime`; `holdings_snapshot`, `buy_list`, `sell_list` stored as PostgreSQL `JSONB`
  - `TradeRecord` — individual order records; `uq_strategy_symbol_date` unique index prevents same-day duplicate buys per symbol
- `src/db.py` — Pydantic sub-models `Holding`, `BuyObj`, `SellObj` for structured JSONB payloads
- `src/db.py` — comprehensive async helper functions: `get_daily_log`, `list_daily_logs`, `get_last_daily_log`, `get_last_unexecuted_daily_log`, `save_strategy_daily_log`, `set_daily_log_to_executed`, `get_today_executed_daily_log`, `get_privous_daily_log`, `check_log_exists_for_post_market`, `update_buy_obj`, `update_sell_obj`, `add_sell_obj`, `save_trade_record`, `is_symbol_traded_today`, `get_activated_strategies`, `get_strategy`, `get_strategies`
- `src/app.py` — registered `scheduler_router` imported from `src.scheduler`
- `src/db_old.py` — archived original SQLite implementation for reference
- `src/db_sync.py` — synchronous PostgreSQL/SQLModel implementation kept for reference

**docker-compose.yml:**

- `postgres` service — `postgres:16-alpine`; port `5436:5432`; health-checked via `pg_isready`; data persisted to `./db/data`; joins `omninance-network`

### Changed

**omninance-backend:**

- `src/db.py` — `init_db()` converted to `async def`; called with `await init_db()` in FastAPI lifespan
- `src/app.py` — lifespan now `await`s `init_db()`; imports `scheduler_router` alongside existing routers
- `pyproject.toml` — added `asyncpg>=0.29.0`; database backend switched from SQLite (`sqlite3`) to PostgreSQL (`postgresql+asyncpg`)

**docker-compose.yml:**

- Added `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` environment variables; `db/` directory ignored via `.gitignore`

---

## [1.7.0] - 2026-04-16

### Added

**omninance-backend:**

- `src/scheduler.py` — APScheduler (`AsyncIOScheduler`) Mon–Fri 14:10 `Asia/Taipei`; triggers chip-tracker pipeline via `POST /api/trigger`, then iterates all active strategies and calls `execute_signals` for each
- `src/db.py` — full schema rewrite replacing the single `execution` table with three tables:
  - `strategy` — stores per-strategy params (`initial_capital`, `partition`, `volume_multiplier`, `concentration_slope`, `atr_multiplier`, `back_test_period`, `status`, `create_at`)
  - `strategy_daily_log` — one row per strategy per trading day (`total_equity`, `available_balance`, `daily_pnl`, `holdings_snapshot`); `UNIQUE(strategy_id, run_date)` prevents duplicate inserts
  - `trade_record` — individual orders (`order_id`, `action CHECK('BUY'|'SELL')`, `status` PENDING/FILLED/PARTIAL/CANCELLED/FAILED/TIMEOUT, `pnl`, `fee`, `return_rate`, `create_at`, `update_at`); indexes on `strategy_id` and `symbol`
  - New helpers: `create_strategy`, `list_strategies`, `stop_strategy`, `insert_daily_log`, `list_daily_logs`, `insert_trade_record` (returns `lastrowid`), `update_trade_record`, `get_trade_records_by_ids`, `get_current_available_balance`, `get_current_holdings`
- `src/routes/strategy.py` — full rewrite to REST endpoints:
  - `POST /api/strategies` — async; creates DB record, immediately executes signals; uses `BackgroundTasks` to register `poll_order_status`
  - `GET /api/strategies` — list all strategies; optional `?status=active|stopped`
  - `POST /api/strategies/{id}/stop` — marks strategy as stopped
  - `GET /api/strategies/{id}/daily-logs` — per-strategy execution history
  - `GET /api/trade-records` — trade record list; optional `?strategy_id=&limit=`
  - `poll_order_status` background task — polls `GET /api/orders` every 5 s; updates records to FILLED / FAILED / TIMEOUT based on broker response

**omninance-chip-tracker:**

- `src/service/signal_generator.py` — extracted `compute_signals(settings)` for in-memory computation (no disk I/O); `generate_signals` now calls `compute_signals` then persists to `dist/`
- `src/routes/signals.py` — `POST /api/signals/compute` — computes signals for arbitrary strategy params without writing to disk; used by omninance-backend scheduler and `create_strategy` endpoint
- `src/service/strategy_reader.py` — reads active strategy settings from shared SQLite DB in read-only URI mode (`?mode=ro`); returns most-recently-created active strategy's params or `None`

**omnitrader:**

- `src/routes/orders.py` — `POST /api/orders/aggressive-limit-order` — calculates a limit price from the current quote plus a configurable tick offset and places a limit buy order; used by omninance-backend's order execution flow

### Changed

**omninance-backend:**

- `src/app.py` — scheduler start/stop wired into FastAPI lifespan; `logging` removed (moved to `start_logging` utility)
- `pyproject.toml` — added `apscheduler>=3.10.0,<4.0`, `pandas`; removed `pyarrow`

**omninance-chip-tracker:**

- `src/app.py` — APScheduler fully removed; pipeline scheduling now owned by omninance-backend; `POST /api/trigger` remains for manual runs
- `src/pipeline.py` — reads active strategy settings from DB via `strategy_reader` before signal generation; falls back to `setting.json` if no active strategy exists

**docker-compose.yml:**

- `chip-tracker` — added `./database:/app/database:ro` volume so `strategy_reader` can access the shared SQLite DB
- `omninance-backend` — replaced `SIGNALS_PATH` env var with `CHIP_TRACKER_URL=http://chip-tracker:8000`; removed signals volume mount; added `depends_on chip-tracker: service_healthy`

**omninance-dashboard:**

- `nginx.conf` — `/api/strategy` replaced by `/api/strategies` and `/api/trade-records`, both routed to `omninance-backend:8000`
- `src/services/traderApi.ts` — exported `StrategyParams` interface; replaced old `strategyStart` / `strategyStop` / `strategyExecutions` with `createStrategy`, `listStrategies`, `stopStrategy`, `getDailyLogs`, `listTradeRecords`
- `src/components/Strategy/ExecutePanel.tsx` — full rewrite: 6-param form (identical params to BacktestPanel); active strategies table with per-row stop buttons; FAILED orders logged immediately; price chart retained
- `src/pages/Strategy.tsx` — Execute tab no longer wrapped in extra `Card`; `ExecutePanel` manages its own card layout

### Removed

- `nginx/default.conf`, `nginx/nginx.conf` — standalone nginx config files removed; `omninance-dashboard/nginx.conf` is the authoritative config
- `omninance-backend/src/db.py` — `execution` table and `insert_execution` / `list_executions` helpers removed (replaced by three-table schema above)
- `omninance-backend/src/routes/strategy.py` — `POST /api/strategy/start`, `POST /api/strategy/stop`, `GET /api/strategy/executions` endpoints removed

---

## [1.6.0] - 2026-04-13

### Added

**omninance-chip-tracker:**

- `src/routes/signals.py` — `GET /api/signals` (reads `dist/latest_signals.json`); `GET /api/price-history` (reads `data/matrix/price_matrix.parquet`; accepts `symbols` and `days` query params)
- `src/main.py` — extracted `compute_portfolio(settings) → (pf, bm_close)` shared helper; all vectorbt matrix loading and portfolio computation now lives here; called by both `run_phase3` (CLI) and the backtest API so logic is never duplicated
- `src/routes/backtest.py` — added `_activity_arrays(pf, n_days)` helper that uses `np.asarray()` on named record columns (works with both numpy structured arrays and pandas DataFrames); computes per-day `buy_count`, `sell_count`, `hold_count` using `np.add.at` for buy/sell and slice accumulation for holding periods; chart rows now include `buy_count`, `sell_count`, `hold_count` integer fields

**omninance-dashboard:**

- `src/components/Strategy/BacktestPanel.tsx` — added daily activity chart below the value chart: `ComposedChart` with blue bars for 買入, red bars for 賣出 (left Y axis), and an orange line for 持倉 count (right Y axis); `ChartRow` interface extended with `buy_count`, `sell_count`, `hold_count`

### Changed

**omninance-chip-tracker:**

- `src/main.py` — `run_phase3` simplified to call `compute_portfolio` + `_report`; `compute_portfolio` is now importable by other modules
- `src/routes/backtest.py` — removed duplicated matrix/portfolio computation; now imports and calls `compute_portfolio` from `src.main`
- `src/app.py` — registered `signals_router`

**omninance-backend:**

- `src/app.py` — removed proxy routers (signals, backtest); now registers only `strategy_router`; added comment clarifying responsibility boundary
- `docker-compose.yml` — removed `MATRIX_PATH`, `CHIP_TRACKER_URL` env vars and matrix volume mount from `omninance-backend`; removed `depends_on chip-tracker`

**omninance-dashboard:**

- `nginx.conf` — `/api/signals`, `/api/price-history`, `/api/backtest`, `/api/trigger` now route directly to `chip-tracker:8000`; `/api/strategy` → `omninance-backend:8000`; `/api` catch-all → `omnitrader:8000`

### Removed

**omninance-backend:**

- `src/routes/signals.py` — signal and price-history serving moved to chip-tracker
- `src/routes/backtest.py` — backtest proxy removed; dashboard queries chip-tracker directly

---

## [1.5.0] - 2026-04-13

### Added

**omninance-backend:**

- `omninance-backend/` — new strategy orchestration service (FastAPI + `uv`)
  - `src/app.py` — FastAPI entry point; initialises SQLite database on startup via lifespan; Swagger UI at `/api-docs`
  - `src/db.py` — SQLite persistence for strategy execution history; `execution` table (`_id`, `action`, `symbol`, `quantity`, `price`, `result`, `error`, `create_date`); `insert_execution` and `list_executions` helpers
  - `src/routes/signals.py` — `GET /api/signals` (reads `latest_signals.json` from chip-tracker dist volume); `GET /api/price-history` (reads `price_matrix.parquet` from chip-tracker matrix volume)
  - `src/routes/strategy.py` — `POST /api/strategy/start` (calculates lots from `initial_capital`, places market buy orders via omnitrader, records results in SQLite); `POST /api/strategy/stop` (fetches inventory from omnitrader, sells held buy-list positions at market, records results in SQLite); `GET /api/strategy/executions` (returns execution history from SQLite)
  - `Dockerfile` — `python:3.12-slim` + `uv`; deps from `pyproject.toml`
  - `pyproject.toml` — `fastapi`, `uvicorn[standard]`, `httpx`, `pandas`, `pyarrow`

**docker-compose.yml:**

- `docker-compose.yml` — added `omninance-backend` service; mounts chip-tracker `dist/` (signals, read-only) and `data/matrix/` (price matrix, read-only); mounts own `data/` for SQLite; injects `SIGNALS_PATH`, `MATRIX_PATH`, `OMNITRADER_URL`; `depends_on` omnitrader health check; `BACKEND_PORT` env var

### Changed

**omnitrader:**

- `src/app.py` — removed `signals` and `price_history` routers; now registers only `orders` and `account` routers (broker API only)
- `pyproject.toml` — removed `pandas` dependency (no longer needed)

**omninance-dashboard:**

- `nginx.conf` — split `/api` routing: `/api/signals`, `/api/price-history`, `/api/strategy` → `omninance-backend:8000`; all other `/api` → `omnitrader:8000`
- `src/services/traderApi.ts` — replaced `executeSignals` and `stopSignals` with `strategyStart`, `strategyStop`, and `strategyExecutions` pointing to the new backend endpoints
- `src/components/Strategy/ExecutePanel.tsx` — updated `handleStart` to call `traderApi.strategyStart({ initial_capital })` and `handleStop` to call `traderApi.strategyStop()`

**docker-compose.yml:**

- `omnitrader` service — removed `SIGNALS_PATH`, `MATRIX_PATH` env vars and chip-tracker signal/matrix volume mounts
- `omninance-dashboard` service — now also depends on `omninance-backend` being healthy

### Removed

**omnitrader:**

- `src/routes/signals.py` — strategy execution logic moved to `omninance-backend`
- `src/routes/price_history.py` — price history serving moved to `omninance-backend`

---

## [1.4.0] - 2026-04-13

### Added

**omnitrader:**

- `src/routes/price_history.py` — new `GET /api/price-history` endpoint; reads `price_matrix.parquet` from `MATRIX_PATH` env (default `/app/matrix`); accepts `symbols` (comma-separated) and `days` (1–365, default 30) query params; returns list of `{ date, <symbol>: float | null }` rows
- `src/routes/signals.py` — added `POST /api/signals/stop` endpoint; sells all symbols from the current buy-list at market price (`PriceFlag.Market`, `price=None`); safeguarded against selling symbols not in current inventory; skipped symbols are reported in response

**omninance-dashboard:**

- `src/components/Strategy/ExecutePanel.tsx` — new execution panel for the Strategy page
  - NT$ initial capital input with auto-calculated lots-per-stock estimate (`floor(capital / count / (avgPrice * 1000))`)
  - 開始策略 / 停止策略 action buttons (market orders via `price_flag: '4'`)
  - Day selector toggle (7 / 14 / 30 / 60 / 90 days)
  - Recharts `LineChart` with prices normalized to 100 at first data point for multi-symbol comparison; `connectNulls` for sparse data

### Changed

**omnitrader:**

- `src/app.py` — registered `price_history_router`

**docker-compose.yml:**

- `omnitrader` service — added `MATRIX_PATH=/app/matrix` env var and `./omninance-chip-tracker/data/matrix:/app/matrix:ro` volume mount so omnitrader can read chip-tracker price matrices

**omninance-dashboard:**

- `package.json` — added `recharts ^2.12.0` dependency
- `src/services/traderApi.ts` — added `post()` helper; added `executeSignals`, `stopSignals`, and `priceHistory` API methods
- `src/pages/Strategy.tsx` — added "執行" card at the bottom of the Strategy page containing `ExecutePanel`

---

## [1.3.0] - 2026-04-10

### Added

- `omninance-dashboard/src/pages/Account.tsx` — previous dashboard content promoted to a dedicated route (`/account`)
- `omninance-dashboard/src/pages/Strategy.tsx` — new strategy page (`/strategy`); reads chip-tracker signal file via `GET /api/signals` and displays metadata card, buy-signal table, and sell-hint table with price and ATR from snapshot

### Changed

- `omninance-dashboard/src/App.tsx` — `/` now redirects to `/account`; added `/strategy` route
- `omninance-dashboard/src/components/Layout/AppShell.tsx` — added fixed bottom navigation (帳戶 / 策略) using `BottomNavigation`; market state chip now shows four Taiwan market states (盤前 / 盤中 / 盤後 / 收市) derived from `is_trading_day` + Asia/Taipei time; chip tooltip shows `public/img/market-time.png`
- `omninance-dashboard/src/components/Inventories/InventoriesTable.tsx` — replaced auto-detected columns with a fixed ordered set and Chinese labels; `s_type` renders 上市 / 上櫃 / 興櫃 instead of H / O / R; 未實現損益 and 獲利率 cells are coloured green/red by sign
- `omninance-dashboard/src/components/CertInfo/CertInfoCard.tsx` — fully typed with `CertInfo` and `KeyInfo` interfaces; `not_after` and `created_at` rendered as formatted dates via `dayjs.unix()`; validity and status shown as colour-coded chips
- `omninance-dashboard/src/services/traderApi.ts` — added `signals` endpoint (`GET /api/signals`)

---

## [1.2.0] - 2026-04-10

### Added

- `omninance-dashboard/` — React + TypeScript + MUI trading dashboard
  - `src/services/traderApi.ts` — typed `fetch` wrappers for all account endpoints
  - `src/hooks/useTraderData.ts` — generic data-fetching hook with loading/error state and auto-refresh (30 s default)
  - `src/components/Layout/AppShell.tsx` — AppBar with market open/closed status chip
  - `src/components/Balance/BalanceCard.tsx` — dynamic key-value balance card with per-row refresh
  - `src/components/TradeStatus/TradeStatusCard.tsx` — trade account status card
  - `src/components/Inventories/InventoriesTable.tsx` — auto-column MUI table for stock holdings
  - `src/components/Settlements/SettlementsTable.tsx` — auto-column MUI table for settlement records
  - `src/components/CertInfo/CertInfoCard.tsx` — two-section card showing certificate and API key info
  - `src/pages/Dashboard.tsx` — 4-tab layout: Overview / Inventories / Settlements / System
  - `nginx.conf` — SPA routing + `/api` reverse-proxied to `omnitrader:8000`
  - `Dockerfile` — `node:21-alpine` build stage → `nginx:alpine` serve stage
- `omnitrader/src/routes/account.py` — added `GET /api/account/cert-info` and `GET /api/account/key-info`
- `docker-compose.yml` — added `omninance-dashboard` service; proxies `/api` through nginx to omnitrader; `depends_on` omnitrader health check; `DASHBOARD_PORT` env var

---

## [1.1.0] - 2026-04-10

### Added

- `omnitrader/` — new E.SUN brokerage trading service (FastAPI + `uv`)
  - `src/sdk_client.py` — SDK singleton; builds config from env vars, pre-populates `CryptFileKeyring`, calls `sdk.login()` on startup and `sdk.logout()` on shutdown
  - `src/routes/orders.py` — `GET /api/orders`, `POST /api/orders`, `POST /api/orders/cancel`, `POST /api/orders/modify-price`
  - `src/routes/account.py` — `GET /api/account/inventories`, `/balance`, `/trade-status`, `/market-status`, `/settlements`, `/transactions`
  - `src/routes/signals.py` — `GET /api/signals` (preview), `POST /api/signals/execute` (executes buy/sell from chip-tracker signal file; sell orders are guarded against non-held stocks)
  - `src/app.py` — FastAPI entry point with Swagger UI at `GET /api-docs`
  - `Dockerfile` — `python:3.12-slim` + `uv`; installs PyPI deps then E.SUN Linux `.whl` files separately
  - `pyproject.toml` — `fastapi`, `uvicorn[standard]`, `keyring`, `keyrings.cryptfile`
  - `.env-example` — all required environment variables documented
- `docker-compose.yml` — added `omnitrader` service; mounts `omnitrader/cert/` (read-only) and `omninance-chip-tracker/dist/` as shared signal volume (read-only); injects `PYTHON_KEYRING_BACKEND` and `KEYRING_CRYPTFILE_PASSWORD`

---

## [1.0.1] - 2026-04-09

### Added

- `omninance-chip-tracker/src/service/signal_generator.py` — reads prebuilt matrices, applies entry logic on the latest two data rows, and writes `dist/signals_YYYYMMDD.json` with `action_date`, `buy_list`, and `sell_list`
- `omninance-chip-tracker/src/pipeline.py` — data pipeline that orchestrates Phase I + Phase II + signal generation; fully separate from the backtest (`main.py`)
- `omninance-chip-tracker/src/app.py` — FastAPI service with APScheduler (Mon–Fri 09:30 `Asia/Taipei`, one automatic retry on failure) and `POST /api/trigger` for manual runs
- `omninance-chip-tracker/Dockerfile` — containerises the FastAPI service using `python:3.12-slim` + `uv`

### Changed

- `omninance-chip-tracker/pyproject.toml` — added `fastapi`, `uvicorn[standard]`, `apscheduler>=3.10,<4.0`
- `docker-compose.yml` — renamed `app` service to `omnindicator`, fixed build context to `./omnindicator`, updated volume path and port env var (`OMNINDICATOR_PORT`); added `chip-tracker` service with `data/` and `dist/` volume mounts and `CHIP_TRACKER_PORT`

---

## [1.0.0] - 2026-04-09 - Separated APP

### Added

- `omninance-chip-tracker/` — new standalone Python service for chip data acquisition and vectorized backtesting
  - Phase I: Incremental OHLCV and large-holder data synchronization per symbol
  - Phase II: Matrix engineering (price, volume, chip slope, ATR parquet matrices)
  - Phase III: Vectorized backtesting via `vectorbt` with ATR trailing stop and cash-sharing portfolio
  - Phase IV: Automated reporting and trade log archiving to `dist/`
- `nginx/` — Nginx reverse proxy configuration (`nginx.conf`, `default.conf`) for multi-service routing

### Changed

- Migrated monolithic root-level app into `omnindicator/` subdirectory with its own `Dockerfile`, `pyproject.toml`, `CLAUDE.md`, `README.md`, and `start.bat`
- Updated `docker-compose.yml` to reference the `omnindicator` service from its subdirectory

### Removed

- Root-level `src/`, `Dockerfile`, `README.md`, `CLAUDE.md`, `pyproject.toml`, `uv.lock`, and `start.bat` (consolidated into `omnindicator/`)

---

## [0.2.0] - 2026-02-04

### Changed

- Refactored monolithic `app.py` into modular `src/` structure
  - `src/indicators/` - Individual indicator modules with `BaseIndicator` base class
  - `src/ui/` - UI rendering module with gauge chart configuration
  - `src/app.py` - Streamlit entry point importing from modules
- Updated `start.bat` to point to `src/app.py`

### Added

- `Dockerfile` for containerized deployment using `uv` and Python 3.12
- `docker-compose.yml` with healthcheck, network, and env mapping
- `.env-example` with default configuration

### Removed

- Root-level `app.py` (moved to `src/app.py`)
- Root-level `main.py` (unused)

## [0.1.0] - 2026-01-29

### Added

- Initial project setup with `uv` and `pyproject.toml`
- Object-oriented indicator framework with `BaseIndicator` abstract class
- Technical indicators implementation:
  - `BiasIndicator` - Price deviation from 20-day SMA
  - `RSIIndicator` - 14-period Relative Strength Index
  - `MACDIndicator` - Moving Average Convergence Divergence histogram
  - `BBIndicator` - Bollinger Bands position percentage
  - `VolumeIndicator` - Volume relative to 20-day average
- Streamlit dashboard with interactive gauge charts
- Stock data fetching via Yahoo Finance API
- Aggregated scoring system for buy/sell/hold recommendations
- Historical data preview tab
- Windows startup script (`start.bat`)
