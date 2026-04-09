omninance-chip-tracker

### 1. Executive Summary

The **Omninance Chip Tracker** is a Python-based quantitative tool designed to identify market anomalies by correlating **abnormal volume** with **large-holder concentration** (Director/Institutional accumulation). The system utilizes a vectorized backtesting engine to validate the "Follow the Smart Money" hypothesis across the entire Taiwan Stock Exchange (TWSE/TPEx).

### 2. Operational Workflow

The CLI application will execute in the following sequence:

#### Phase I: Data Acquisition & Synchronization

- **Target Selection:** Load `data/stock_list.csv` to identify active tickers.
- **Incremental Update:** Check `data/setting.json` or file metadata for the `last_updated` timestamp. Skip tickers already updated today to avoid IP rate-limiting.
- **Service Execution:
  - `stock_data.py`: Fetch OHLCV via `yfinance`.
  - `holder_data.py`: 
	- Scrape shareholder distribution via `twsthr.info`.
	- Calculate Linear Regression Slope of large holders month diff via `calc_slope()`
- **Storage:** Save individual results to `data/raw/` in CSV format for manual verification.

#### Phase II: Matrix Engineering


- **Alignment:** Transform individual CSVs into four Master Matrices: `Price`, `Volume`, and `Chip Diff Slope` and `ATR`.
- **Resampling:** Forward-fill (`ffill`) weekly chip data to match daily price frequency.
- **Optimization:** Export aligned DataFrames to `.parquet` in `data/matrix/` for high-speed I/O.

#### Phase III: Vectorized Backtesting

- **Configuration:** Read strategy parameters (e.g., initial_capital, partition, volume_multiplier, concentration_slope, atr_multiplier) from `data/setting.json`.
- **Signal Generation:** Execute vectorized logic: `(Volume > MA20 * volume_multiplier) & (Chip Diff Slope > concentration_slope)`.
- **Simulation:** Run `vbt.Portfolio.from_signals` with a 100,000 TWD initial capital and cash sharing.
  - When signal emit, add one part of capital into signal stock
  - Use `ATR * atr_multiplier` to determine trailing stop point.
- **Benchmarking:** Concurrent simulation of a "Buy and Hold" strategy for **0050.TW** over the same period.

#### Phase IV: Reporting & Archiving

- **CLI Output:** Print summary statistics (Sharpe Ratio, Max Drawdown, Total Return vs. Benchmark).
- **Export:** Save the detailed trade log and performance metrics to `dist/backtest_{timestamp}.csv`.

### 3. Implementation Checklist & Technical Details

|**Task**|**Module**|**Key Technology**|
|---|---|---|
|**Incremental Scraper**|`stock_data.py`|`yfinance`, `pathlib.Path.stat`|
|**Chip Scraper**|`holder_data.py`|`requests`, `pandas.read_html`|
|**Matrix Builder**|`src/service/`|`pandas.concat`, `df.reindex(method='ffill')`|
|**Backtest Engine**|`src/main.py`|`vectorbt`, `numpy`|
|**Benchmark Integration**|`src/main.py`|`vbt.Portfolio.from_holding` (0050.TW)|

### 4. project structure

./
./pyproject.toml
./start.bat
./src/
./src/service/
./src/service/stock_data.py
./src/service/holder_data.py
./data/
./data/stock_list.csv
./data/raw/
./data/raw/holders/
./data/raw/holders/2330_TW_holders.csv
./data/raw/tickers/
./data/raw/tickers/2330_TW.csv
./data/matrix/
./data/matrix/price_matrix.parquet
./data/matrix/volume_matrix.parquet
./data/matrix/chip_matrix.parquet
./data/setting.json
./dist/
./dist/backtest_03_31_26_1612.csv

### 5. setting.json initial value

{
  "initial_capital": 100000,
  "partition": 100,
  "volume_multiplier": 2,
  "concentration_slope": 50,
  "atr_multiplier": 2,
  "back_test_period": 4
}