# CLAUDE.md

Agent guidelines for the Omninance project.

## Project Overview

Omninance is a Python-based stock analysis dashboard using Streamlit. It calculates multiple technical indicators and provides buy/sell/hold recommendations through an aggregated scoring system.

## Tech Stack

- **Language**: Python 3.12+
- **Package Manager**: `uv` (MUST use `uv`, NOT `pip` or `requirements.txt`)
- **Web Framework**: Streamlit
- **Data Source**: Yahoo Finance (`yfinance`)
- **Technical Analysis**: `pandas-ta`
- **Visualization**: ECharts via `streamlit-echarts`

## Commands

```bash
# Install dependencies
uv sync

# Run application
uv run streamlit run src/app.py

# Or use startup script (Windows)
start.bat

# Docker
docker compose up --build
```

## Architecture

### Project Structure

```
src/
├── app.py              # Main Streamlit application entry point
├── indicators/         # Technical indicator modules
│   ├── __init__.py     # Re-exports all indicators
│   ├── base_indicator.py
│   ├── bias_indicator.py
│   ├── rsi_indicator.py
│   ├── macd_indicator.py
│   ├── bb_indicator.py
│   └── volume_indicator.py
└── ui/                 # UI rendering modules
    ├── __init__.py     # Re-exports UI functions
    └── gauge_chart.py  # ECharts gauge chart configuration
```

### Indicator Framework

All indicators extend `BaseIndicator` (defined in `src/indicators/base_indicator.py`):

```python
class BaseIndicator(ABC):
    def __init__(self, name):
        self.name = name
        self.value = 0.0      # Current indicator value
        self.score = 0        # Score: -1 (bearish), 0 (neutral), 1 (bullish)
        self.min_val = 0.0    # Gauge minimum
        self.max_val = 100.0  # Gauge maximum

    @abstractmethod
    def calculate(self, df):
        """Calculate indicator value and score from DataFrame"""
        pass
```

### Current Indicators

| Indicator | Bullish (+1) | Bearish (-1) |
|-----------|--------------|--------------|
| BIAS | < -3% | > 3% |
| RSI | < 30 | > 70 |
| MACD | Histogram > 0 | Histogram < 0 |
| Bollinger | < 20% position | > 80% position |
| Volume | > 1.2x average | - |

## Adding New Indicators

1. Create a new file in `src/indicators/` extending `BaseIndicator`
2. Implement the `calculate(df)` method
3. Set `self.value` and `self.score` in the method
4. Export the class in `src/indicators/__init__.py`
5. Add instance to `indicator_list` in `src/app.py`

## Norms

Always follow guidelines in `/norm` directory before making changes.
