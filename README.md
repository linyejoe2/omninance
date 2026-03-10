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
- Docker & Docker Compose (optional, for containerized deployment)

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
uv run streamlit run src/app.py
```

### Docker

```bash
cp .env-example .env
docker compose up --build
```

The application will be available at `http://localhost:8501`.

## Architecture

```
omninance/
├── src/
│   ├── app.py                  # Main Streamlit application
│   ├── indicators/
│   │   ├── __init__.py
│   │   ├── base_indicator.py   # BaseIndicator abstract class
│   │   ├── bias_indicator.py   # BIAS indicator
│   │   ├── rsi_indicator.py    # RSI indicator
│   │   ├── macd_indicator.py   # MACD indicator
│   │   ├── bb_indicator.py     # Bollinger Bands indicator
│   │   └── volume_indicator.py # Volume indicator
│   └── ui/
│       ├── __init__.py
│       └── gauge_chart.py      # ECharts gauge rendering
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml              # Project configuration & dependencies
├── uv.lock                     # Lock file
├── start.bat                   # Windows startup script
├── .env-example                # Environment variable template
├── norm/                       # Development norms & guidelines
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
