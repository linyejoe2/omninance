# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Omninance is a Python-based stock analysis dashboard using Streamlit. It calculates multiple technical indicators and provides buy/sell/hold recommendations through an aggregated scoring system, with a backtest engine for strategy validation.

## Tech Stack

- **Language**: Python 3.12+
- **Package Manager**: `uv` (MUST use `uv`, NOT `pip` or `requirements.txt`)
- **Web Framework**: Streamlit
- **Data Source**: Yahoo Finance (`yfinance`)
- **Technical Analysis**: `pandas-ta`
- **Visualization**: Plotly (indicator plots) + ECharts via `streamlit-echarts` (gauge charts)
- **Database**: SQLite via `database/omninance.db`

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

### Module Overview

```
src/
├── app.py                    # Main Streamlit app: sidebar, symbol search, tabs
├── db.py                     # Database singleton (db); manages SQLite tables for history, stock list, business cycle, holders
├── stock_data.py             # fetch_stock_data(): cached yfinance fetcher with incremental updates
├── util.py                   # bounded_cumsum(): bounded cumulative sum helper
├── indicators/
│   ├── base_indicator.py     # BaseIndicator ABC
│   ├── indicator_script.py   # get_indicators(symbol), get_total_scores() — cached indicator factory
│   └── ...                   # Individual indicator modules
├── ui/
│   ├── gauge_chart.py        # ECharts gauge chart config
│   └── render_indicator.py   # render_indicator_settings(): dynamic parameter UI + plots
└── backtest/
    └── backtester.py         # BacktestEngine: run() and calculate_metrics()
```

### Indicator Framework

All indicators extend `BaseIndicator` (`src/indicators/base_indicator.py`):

```python
class BaseIndicator(ABC):
    def __init__(self, name, weight=1.0, min_val=0.0, max_val=100.0, color="#5470c6"):
        self.current_value = 0.0   # Last value (for gauge display)
        self.score = 0             # Last score (for summary gauge)

    @abstractmethod
    def compute_series(self, df: pd.DataFrame) -> pd.Series:
        """Return raw indicator value series (e.g. RSI curve)"""

    @abstractmethod
    def compute_score(self, series: pd.Series) -> pd.Series:
        """Convert value series to score series (range: -100 to 100)"""

    def calculate(self, df):
        """Calls compute_series → compute_score, updates current_value/score, returns (val_series, score_series)"""

    def render_plot(self, df):
        """Renders a Plotly chart (value + score subplots) via st.plotly_chart"""
```

### Current Indicators

| Indicator | Class | Bullish (+100) | Bearish (-100) | Data Source |
|-----------|-------|----------------|----------------|-------------|
| BIAS | `BiasIndicator` | Price far below MA | Price far above MA | yfinance |
| RSI | `RSIIndicator` | < 30 | > 70 | yfinance |
| MACD | `MACDIndicator` | Histogram > 0 | Histogram < 0 | yfinance |
| Bollinger | `BBIndicator` | %B < 20% | %B > 80% | yfinance |
| Volume | `VolumeIndicator` | > 1.2x avg | — | yfinance |
| 景氣燈號 | `BusinessCycleIndicator` | Score 23-37 | Score ≤ 16 | NDC Excel sync |
| 大戶籌碼 | `LargeHolderIndicator` | Rising 400+ lot holders | Declining | norway.twsthr.info scrape |

### Adding New Indicators

1. Create `src/indicators/<name>_indicator.py` extending `BaseIndicator`
2. Implement `compute_series(df)` and `compute_score(series)` — scores should be in the -100 to 100 range
3. Export from `src/indicators/__init__.py`
4. Add instance to the list in `src/indicators/indicator_script.py::get_indicators()`

### Data Flow

1. `fetch_stock_data(symbol)` → loads from SQLite cache, fetches delta from yfinance if stale
2. `get_indicators(symbol)` → `@st.cache_resource` cached list of indicator instances
3. `render_indicator_settings()` → auto-generates Streamlit parameter UI from indicator `__dict__`, calls `indicator.render_plot(df)`
4. `get_total_scores(df, indicators)` → weighted average of scores across all indicators
5. `BacktestEngine.run()` → builds score matrix, applies `bounded_cumsum` for position sizing

### Database Tables

| Table | Purpose |
|-------|---------|
| `search_history` | Symbol lookup history with pin/time ordering |
| `stock_list` | Taiwan stock symbols + names (from TWSE) |
| `business_indicators` | Monthly NDC business cycle scores |
| `sync_log` | Last sync date per stock (prevents redundant fetches) |
| `stock_holders_<code>` | Per-stock large holder history (scraped weekly) |
| `<ticker_with_underscore>` | OHLCV price data per symbol |

## Norms

Always read and follow guidelines in the `/norm` directory before making changes. Start with `/norm/00-manifest.md` for loading order. Key rules:
- Use `uv` with `pyproject.toml` — `requirements.txt` is prohibited
- Database columns use `snake_case`; do not use plural table names
- Do not refactor existing code structure to match norms — apply norms only to new code
