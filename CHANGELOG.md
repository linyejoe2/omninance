# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

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
