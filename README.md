# Omninance

A multi-service Taiwan stock trading platform: chip-tracking data pipeline + backtesting, an E.SUN brokerage trading service, a strategy-orchestration backend, and a React dashboard — all orchestrated with Docker Compose.

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
├── ofelia.ini               # Ofelia scheduler job config (data refreshes + post-market strategy jobs)
├── norm/                    # Development norms (read before making changes)
└── ChangeLog.md
```

## Services

| Service | Purpose | Port var |
| --- | --- | --- |
| `omnindicator` | Streamlit dashboard for technical indicators & per-symbol backtesting | `OMNINDICATOR_PORT` |
| `omninance-chip-tracker` | Data pipeline (chip/holder/OHLCV) + vectorised backtest + signal generation | `CHIP_TRACKER_PORT` |
| `omnitrader` | E.SUN brokerage SDK wrapper — places/manages orders | `OMNITRADER_PORT` |
| `omninance-backend` | Strategy CRUD/execution (PostgreSQL) + read-only data explorer (MongoDB) | `BACKEND_PORT` |
| `omninance-dashboard` | React dashboard — account, strategy, and data-explorer UI | `DASHBOARD_PORT` |
| `mongodb` | Shared datastore for tracked-stock data (`tickers`, `holders`, `stock_list`) | `MONGO_PORT` |
| `postgres` | Strategy/execution persistence for `omninance-backend` | — |
| `scheduler` | Ofelia cron container — all data-refresh and post-market strategy job triggers | — |
| `autoheal` | Restarts unhealthy containers | — |

See each service's own `CLAUDE.md`/`README.md` for endpoint-level detail.

## Data storage

Since v2.0.0 ("Remake"), tracked-stock data lives in a single shared **MongoDB** instance instead of scattered per-service CSV/parquet files:

- `tickers` — daily OHLCV per symbol (unique index on `symbol` + `date`)
- `holders` — 大股東持股 concentration history per symbol (unique index on `symbol` + `date`)
- `stock_list` — the tracked stock universe, ranked by market cap (unique index on `symbol`)

`omninance-chip-tracker` owns writes (via its data pipeline and `scripts/migrate_csv_to_mongo.py`, a one-time CSV → Mongo backfill); `omninance-backend` reads the same collections through its data-explorer endpoints and refreshes `stock_list`/`tickers`/`holders` via `yfinance`/TDCC scraping on hourly `scheduler` (Ofelia) triggers.

Strategy/execution data (`strategy`, `strategy_daily_log`, `trade_record`) remains in **PostgreSQL**, owned by `omninance-backend`.

## Prerequisites

- Docker & Docker Compose
- Python 3.12 + [`uv`](https://docs.astral.sh/uv/) (for running a service outside Docker)
- Node 18+ (for `omninance-dashboard` outside Docker)

## Quick start

```bash
cp .env-example .env   # fill in the keys below
docker compose up --build
```

## Environment variables

```bash
# Service ports
OMNINDICATOR_PORT=8501
CHIP_TRACKER_PORT=8001
OMNITRADER_PORT=8002
BACKEND_PORT=8003
DASHBOARD_PORT=3000

# MongoDB (shared tracked-stock datastore)
MONGO_PORT=27017
MONGO_USERNAME=...
MONGO_PASSWORD=...
MONGO_DB=...
MONGO_DB_NAME=...

# PostgreSQL (omninance-backend strategy/execution store)
POSTGRES_USER=...
POSTGRES_PASSWORD=...
POSTGRES_DB=...

# omnitrader (E.SUN brokerage)
KEYRING_CRYPTFILE_PASSWORD=...
ESUN_ENTRY=...
ESUN_API_KEY=...
ESUN_API_SECRET=...
ESUN_ACCOUNT=...
ESUN_ACCOUNT_PASSWORD=...
ESUN_CERT_PATH=/app/cert/esun.p12
ESUN_CERT_PASSWORD=...
```

## Scheduler

The `scheduler` container (`mcuadros/ofelia:latest`) runs every recurring `omninance-backend` job defined in `ofelia.ini` — there is no in-process scheduler in the app itself:

- `stock-list-refresh` / `ticker-refresh` / `holder-refresh` — hourly; each endpoint no-ops until its underlying data (yfinance market cap, TWSE/TPEx bars, TDCC 股權分散表) is actually stale, so real refreshes happen less often than the trigger fires.
- `daily-strategies` / `finalize-daily-settlement` / `compute-signals` — Mon–Fri 10:04 / 15:00 / 15:30 `Asia/Taipei`; execute buy/sell for pending signals, settle equity/PnL, and compute next-day signals for every active strategy.

Every job's execution history is recorded in the `schedule_log` collection and viewable (with manual force-execute) on the dashboard's 排程 page — see `GET /api/schedules` and `POST /api/schedules/{job}/trigger`.

## Norms

Read `/norm` (start with `norm/00-manifest.md`) before making changes — naming conventions, backend/frontend/docker-compose standards, and the documentation-update workflow all live there.

## Author

Randy Lin
