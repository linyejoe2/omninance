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
uv run streamlit run app.py

# Or use startup script (Windows)
start.bat
```

## Architecture

### Indicator Framework

All indicators extend `BaseIndicator` (defined in `app.py`):

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

1. Create a class extending `BaseIndicator`
2. Implement the `calculate(df)` method
3. Set `self.value` and `self.score` in the method
4. Add instance to `indicator_list` in the main app

## Norms

Always follow guidelines in `/norm` directory before making changes.
