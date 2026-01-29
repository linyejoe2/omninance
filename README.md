# Omninance

A multi-indicator stock analysis dashboard built with Streamlit and Python.

## Features

- **Object-Oriented Indicator Framework**: Extensible `BaseIndicator` class for building technical indicators
- **Technical Indicators**: BIAS, RSI, MACD, Bollinger Bands, Volume analysis
- **Scoring System**: Each indicator produces a score (-1, 0, +1) for aggregated buy/sell signals
- **Interactive Dashboard**: Real-time gauge charts powered by ECharts
- **Stock Data**: Fetches historical data via Yahoo Finance API

## Prerequisites

- Python >= 3.12
- [uv](https://docs.astral.sh/uv/) - Python package manager

## Installation

```bash
uv sync
```

## Usage

### Windows

```bash
start.bat
```

### Manual

```bash
uv run streamlit run app.py
```

The application will be available at `http://localhost:8501`.

## Architecture

```
omninance/
├── app.py              # Main Streamlit application
├── main.py             # CLI entry point
├── pyproject.toml      # Project configuration & dependencies
├── uv.lock             # Lock file
├── start.bat           # Windows startup script
├── norm/               # Development norms & guidelines
└── README.md
```

## Dependencies

- `streamlit` - Web dashboard framework
- `yfinance` - Yahoo Finance API client
- `pandas` / `pandas-ta` - Data analysis & technical indicators
- `streamlit-echarts` - ECharts integration for Streamlit
- `plotly` - Interactive charting

## Author

Randy Lin
