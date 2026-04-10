# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

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
