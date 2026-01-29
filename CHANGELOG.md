# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

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
