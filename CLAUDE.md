# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Omninance is a multi-service Taiwan stock trading platform composed of five application services (omnindicator, omninance-chip-tracker, omnitrader, omninance-backend, omninance-dashboard) plus supporting infrastructure containers (MongoDB, PostgreSQL, an Ofelia cron scheduler, autoheal), all orchestrated via Docker Compose. As of v2.0.0 ("Remake"), MongoDB is the shared datastore for tracked-stock data (tickers, holders, stock list) — replacing the CSV files chip-tracker previously wrote to disk — while PostgreSQL remains the store for strategy/execution data.

## Architecture

```
omninance/
├── omnindicator/            # Streamlit technical-indicator dashboard
├── omninance-chip-tracker/  # Chip-tracking data pipeline + backtesting + signal generation
├── omnitrader/              # E.SUN brokerage API trading service
├── omninance-backend/       # Strategy orchestration + MongoDB-backed data explorer API
├── omninance-dashboard/     # React trading dashboard (account info + strategy signals + data explorer)
├── nginx/                   # Shared Nginx reverse-proxy config
├── database/                # Bind-mounted MongoDB / PostgreSQL / SQLite data volumes
├── docker-compose.yml       # Multi-service orchestration
├── ofelia.ini               # Ofelia scheduler job config (hourly stock-list refresh)
├── norm/                    # Development norms (read before making changes)
└── CHANGELOG.md
```

## Services

### omnindicator
- **Purpose**: Streamlit dashboard for technical indicators and per-symbol backtesting
- **Stack**: Python 3.12, `uv`, Streamlit, yfinance, pandas-ta, SQLite
- **Run**: `cd omnindicator && uv run streamlit run src/app.py`
- **Docker port**: `OMNINDICATOR_PORT` → 8501

### omninance-chip-tracker
- **Purpose**: Data pipeline (Phase I–II) + vectorised backtest (Phase III) + signal generation; no internal scheduler. Ticker (OHLCV), holder-concentration, and tracked stock-list data are persisted to MongoDB (`src/models/db.py`, `motor`) instead of CSV; `scripts/migrate_csv_to_mongo.py` is the one-time CSV→Mongo backfill
- **Stack**: Python 3.12, `uv`, FastAPI, vectorbt, yfinance, pandas-ta, motor (MongoDB)
- **Endpoints**:
  - `GET  /health`
  - `POST /api/trigger` — manual pipeline run (also called by omninance-backend scheduler)
  - `GET  /api/signals` — latest signal file
  - `GET  /api/price-history` — daily close prices from price matrix
  - `POST /api/signals/compute` — compute signals in-memory for given params (no disk write)
  - `POST /api/backtest` — run vectorbt backtest and return stats + chart data
- **Signal output**: `dist/signals_YYYYMMDD.json` + `dist/latest_signals.json`
- **Run**: `cd omninance-chip-tracker && uv run uvicorn src.app:app`
- **Docker port**: `CHIP_TRACKER_PORT` → 8000

### omnitrader
- **Purpose**: E.SUN brokerage SDK wrapper — places and manages orders (broker API only)
- **Stack**: Python 3.12, `uv`, FastAPI, keyring (CryptFileKeyring), esun_trade SDK
- **Key env vars**: `ESUN_ENTRY`, `ESUN_API_KEY`, `ESUN_API_SECRET`, `ESUN_ACCOUNT`, `ESUN_ACCOUNT_PASSWORD`, `ESUN_CERT_PATH`, `ESUN_CERT_PASSWORD`
- **Endpoints**:
  - `GET  /health`
  - `GET  /api-docs` — Swagger UI
  - `GET  /api/orders` — today's orders
  - `POST /api/orders` — place order
  - `POST /api/orders/cancel` — cancel order
  - `POST /api/orders/modify-price`
  - `POST /api/orders/aggressive-limit-order` — place limit order at quote + tick offset
  - `GET  /api/account/inventories`
  - `GET  /api/account/balance`
  - `GET  /api/account/trade-status`
  - `GET  /api/account/market-status`
  - `GET  /api/account/settlements`
  - `GET  /api/account/transactions`
  - `GET  /api/account/cert-info`
  - `GET  /api/account/key-info`
- **Run**: `cd omnitrader && uv run uvicorn src.app:app`
- **Docker port**: `OMNITRADER_PORT` → 8000

### omninance-backend
- **Purpose**: Strategy orchestration — CRUD for strategies, daily execution, PostgreSQL persistence, APScheduler; also exposes a read-only "data explorer" over chip-tracker's MongoDB-backed stock data, plus a `yfinance` refresher for the tracked stock list
- **Stack**: Python 3.12, `uv`, FastAPI, APScheduler, httpx, pandas, motor, pymongo, yfinance
- **Scheduler**: Mon–Fri 14:10 `Asia/Taipei` — triggers chip-tracker pipeline, then executes all active strategies
- **DB**: PostgreSQL (`postgres` service, SQLModel + `asyncpg`) for strategy/execution data — tables: `strategy`, `strategy_daily_log`, `trade_record`. MongoDB (`omninance-db`, `motor`) for read-only stock/ticker/holder data — collections: `tickers`, `holders`, `stock_list`
- **Endpoints**:
  - `GET  /health`
  - `POST /api/strategies` — create strategy + execute signals immediately
  - `GET  /api/strategies` — list strategies (`?status=active|stopped`)
  - `POST /api/strategies/{id}/stop` — deactivate strategy
  - `GET  /api/strategies/{id}/daily-logs` — per-strategy execution history
  - `GET  /api/trade-records` — trade records (`?strategy_id=&limit=`)
  - `GET  /api/stock-list` — all tracked symbols (MongoDB `stock_list`)
  - `GET  /api/stock-list/{symbol}/tickers` — OHLCV history for a symbol
  - `GET  /api/stock-list/{symbol}/holders` — holder concentration history for a symbol
  - `POST /api/stock-list/refresh` — refresh `stock_list` entries whose `updated_at` is stale via `yfinance` (`?max_age_hours=`, default 12); called hourly by the `scheduler` container
- **Run**: `cd omninance-backend && uv run uvicorn src.app:app`
- **Docker port**: `BACKEND_PORT` → 8000

### mongodb
- **Purpose**: Shared datastore for tracked-stock data — `tickers`, `holders`, `stock_list` collections; written/migrated by omninance-chip-tracker, read by omninance-chip-tracker and omninance-backend's data-explorer/refresh endpoints
- **Image**: `mongo:8.0` (container `omninance-db`)
- **Indexes**: unique compound `(symbol, date)` on `tickers` and `holders`; unique `symbol` on `stock_list`
- **Data**: persisted to `./database/data/db`
- **Docker port**: `MONGO_PORT` → 27017

### scheduler
- **Purpose**: Cron-style job runner — hourly triggers `POST /api/stock-list/refresh` on omninance-backend so the tracked stock list stays fresh without a scheduler baked into the app
- **Image**: `mcuadros/ofelia:latest` (container `omninance-scheduler`)
- **Config**: `ofelia.ini` (mounted read-only), `depends_on omninance-backend: service_healthy`

### omninance-dashboard
- **Purpose**: React trading dashboard — account overview, inventories, settlements, strategy management, MongoDB data explorer
- **Stack**: React 18, TypeScript, Vite, MUI v5, react-router-dom v6, dayjs, recharts
- **Pages**:
  - `/account` — Overview / Inventories / Settlements / System tabs
  - `/strategy` — Overview (latest signals) / Backtest / Execute tabs
  - `/data` — tracked stock-list table with search/sort/pagination; row click opens a drawer with per-symbol ticker/holder history
- **API proxy**: nginx routes by prefix — `/api/signals`, `/api/price-history`, `/api/backtest`, `/api/trigger` → `chip-tracker`; `/api/strategies`, `/api/trade-records`, `/api/stock-list` → `omninance-backend`; `/api` catch-all → `omnitrader`
- **Run**: `cd omninance-dashboard && npm run dev`
- **Docker port**: `DASHBOARD_PORT` → 80

## Docker Compose

```bash
# Start all services
docker compose up --build

# Required .env keys (see omnitrader/.env-example for full list)
OMNINDICATOR_PORT=8501
CHIP_TRACKER_PORT=8001
OMNITRADER_PORT=8002
BACKEND_PORT=8003
DASHBOARD_PORT=3000
MONGO_PORT=27017
MONGO_USERNAME=...
MONGO_PASSWORD=...
MONGO_DB=...
MONGO_DB_NAME=...
KEYRING_CRYPTFILE_PASSWORD=...
ESUN_ENTRY=...
ESUN_API_KEY=...
ESUN_API_SECRET=...
ESUN_ACCOUNT=...
ESUN_ACCOUNT_PASSWORD=...
ESUN_CERT_PATH=/app/cert/esun.p12
ESUN_CERT_PASSWORD=...
```

## Norms

Always read and follow guidelines in the `/norm` directory before making changes. Start with `/norm/00-manifest.md` for loading order. Key rules:
- Use `uv` with `pyproject.toml` for Python services — `requirements.txt` is prohibited
- Use React + TypeScript + Vite + MUI for frontend services
- Database columns use `snake_case`; do not use plural table names
- API URLs use `/api` prefix with kebab-case plural nouns
- Do not refactor existing code structure to match norms — apply norms only to new code
