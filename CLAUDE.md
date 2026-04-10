# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Omninance is a multi-service Taiwan stock trading platform composed of four containerised services orchestrated via Docker Compose.

## Architecture

```
omninance/
├── omnindicator/            # Streamlit technical-indicator dashboard
├── omninance-chip-tracker/  # Chip-tracking data pipeline + backtesting + signal generation
├── omnitrader/              # E.SUN brokerage API trading service
├── omninance-dashboard/     # React trading dashboard (account info + strategy signals)
├── nginx/                   # Shared Nginx reverse-proxy config
├── docker-compose.yml       # Multi-service orchestration
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
- **Purpose**: Scheduled data pipeline (Phase I–II) + vectorised backtest (Phase III) + daily signal generation
- **Stack**: Python 3.12, `uv`, FastAPI, APScheduler, vectorbt, yfinance, pandas-ta
- **Scheduler**: Mon–Fri 09:30 Asia/Taipei — runs pipeline, retries once on failure
- **Endpoints**:
  - `GET  /health`
  - `POST /api/trigger` — manual pipeline run
- **Signal output**: `dist/signals_YYYYMMDD.json` + `dist/latest_signals.json`
- **Run**: `cd omninance-chip-tracker && uv run uvicorn src.app:app`
- **Docker port**: `CHIP_TRACKER_PORT` → 8000

### omnitrader
- **Purpose**: E.SUN brokerage SDK wrapper — places and manages orders, reads signals
- **Stack**: Python 3.12, `uv`, FastAPI, keyring (CryptFileKeyring), esun_trade SDK
- **Key env vars**: `ESUN_ENTRY`, `ESUN_API_KEY`, `ESUN_API_SECRET`, `ESUN_ACCOUNT`, `ESUN_ACCOUNT_PASSWORD`, `ESUN_CERT_PATH`, `ESUN_CERT_PASSWORD`
- **Endpoints**:
  - `GET  /health`
  - `GET  /api-docs` — Swagger UI
  - `GET  /api/orders` — today's orders
  - `POST /api/orders` — place order
  - `POST /api/orders/cancel` — cancel order
  - `POST /api/orders/modify-price`
  - `GET  /api/account/inventories`
  - `GET  /api/account/balance`
  - `GET  /api/account/trade-status`
  - `GET  /api/account/market-status`
  - `GET  /api/account/settlements`
  - `GET  /api/account/transactions`
  - `GET  /api/account/cert-info`
  - `GET  /api/account/key-info`
  - `GET  /api/signals` — preview latest signal file
  - `POST /api/signals/execute` — execute buy/sell from signal file
- **Run**: `cd omnitrader && uv run uvicorn src.app:app`
- **Docker port**: `OMNITRADER_PORT` → 8000

### omninance-dashboard
- **Purpose**: React trading dashboard — account overview, inventories, settlements, strategy signals
- **Stack**: React 18, TypeScript, Vite, MUI v5, react-router-dom v6, dayjs
- **Pages**:
  - `/account` — Overview / Inventories / Settlements / System tabs
  - `/strategy` — chip-tracker signal viewer (buy list, sell hints, snapshot prices)
- **API proxy**: nginx forwards `/api` → `omnitrader:8000` (no CORS)
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
DASHBOARD_PORT=3000
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
