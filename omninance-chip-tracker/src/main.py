import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import vectorbt as vbt
import yfinance as yf

from src.service.holder_data import (
    sync_stock_holder_data,
    check_newest_date,
    get_newest_stock_holder_data,
    get_stock_large_holder_percentage,
)
from src.service.matrix_builder import build_matrices
from src.service.stock_data import download_tickers

from src.util import get_TSC_top_series_by_market_cap, get_OTC_top_series_by_market_cap, Tee
from src.CONST import STOCK_LIST_PATH



ROOT = Path(__file__).parent.parent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_settings() -> dict:
    return json.loads((ROOT / "data" / "setting.json").read_text())


def load_symbols() -> list[str]:
    df = pd.read_csv(STOCK_LIST_PATH)
    return df["symbol"].dropna().drop_duplicates().tolist()

def update_stock_list():
    TSC_df = get_TSC_top_series_by_market_cap(200)
    TSC_df["symbol"] = TSC_df["symbol"].astype("string") + ".TW"
    OTC_df = get_OTC_top_series_by_market_cap(50)
    OTC_df["symbol"] = OTC_df["symbol"].astype("string") + ".TWO"
    
    combined_df = pd.concat([TSC_df, OTC_df], axis=0, ignore_index=True)
    combined_df["date"] = combined_df["date"].bfill().ffill().astype(int)
    combined_df["date"] = combined_df["date"].apply(lambda x: x+19110000)
    combined_df["date"] = pd.to_datetime(combined_df["date"], format="%Y%m%d").dt.date
    combined_df = combined_df.set_index("symbol")
    
    df = pd.read_csv(STOCK_LIST_PATH).fillna("").drop_duplicates('symbol').set_index('symbol')
    
    df = df.combine_first(combined_df)
    df = df.astype(object).fillna("")
    
    
    df.to_csv(STOCK_LIST_PATH)



def is_updated_today(path: Path) -> bool:
    if not path.exists():
        return False
    mtime = datetime.fromtimestamp(path.stat().st_mtime)
    return mtime.date() == datetime.today().date()


# ---------------------------------------------------------------------------
# Phase I — Data Acquisition & Synchronization
# ---------------------------------------------------------------------------

def run_phase1(symbols: list[str], settings: dict):
    print("\n[Phase I] Data Acquisition & Synchronization")

    raw_tickers = ROOT / "data" / "raw" / "tickers"
    raw_holders = ROOT / "data" / "raw" / "holders"
    raw_tickers.mkdir(parents=True, exist_ok=True)
    raw_holders.mkdir(parents=True, exist_ok=True)

    years = settings.get("back_test_period", 4)
    start_date = (datetime.today() - timedelta(days=years * 365)).strftime("%Y-%m-%d")

    newest_date_cache: str | None = None  # resolved once in step 3, reused for all stocks

    for symbol in symbols:
        file_key = symbol.replace(".", "_")

        # OHLCV
        ticker_path = raw_tickers / f"{file_key}.csv"
        if not is_updated_today(ticker_path):
            print(f"  Downloading OHLCV:  {symbol}")
            df = download_tickers(symbol, start=start_date)
            if not df.empty:
                df.to_csv(ticker_path)
        else:
            print(f"  Skip OHLCV (today): {symbol}")

        # --- Holders: 5-step incremental update ---
        holder_path = raw_holders / f"{file_key}_holders.csv"

        # Step 1: file doesn't exist → Step 2 (full history)
        if not holder_path.exists():
            print(f"  [New] Full holder history:     {symbol}")
            df_holder = sync_stock_holder_data(symbol)
            if df_holder is not None and not df_holder.empty:
                df_holder.to_csv(holder_path, index=False, encoding="utf-8-sig")
            continue

        # Step 3: resolve newest published date (cached)
        if newest_date_cache is None:
            print(f"  Checking newest holder date...")
            newest_date_cache = check_newest_date(symbol)
            if newest_date_cache is None:
                print("  [Warn] Cannot reach twsthr.info — skipping holder updates")
                break

        df_local = pd.read_csv(holder_path, encoding="utf-8-sig", dtype={"資料日期": str})
        local_last = df_local["資料日期"].iloc[0]

        if local_last >= newest_date_cache:
            print(f"  Skip holders (up to date):       {symbol}")
            continue

        # Step 4: one-day parquet — download once, reuse for all stocks
        date_label = pd.to_datetime(newest_date_cache, format="%Y%m%d").strftime("%m_%d_%y")
        one_day_path = raw_holders / "one_day" / f"{date_label}.parquet"

        if not one_day_path.exists():
            print(f"  Downloading one-day snapshot ({newest_date_cache})...")
            get_newest_stock_holder_data(one_day_path)

        # Step 5: prepend new row to holders CSV
        new_row = get_stock_large_holder_percentage(symbol, one_day_path)
        if new_row is not None:
            updated = pd.concat([pd.DataFrame([new_row]), df_local], ignore_index=True)
            updated.to_csv(holder_path, index=False, encoding="utf-8-sig")
            print(f"  Updated holders:                 {symbol}")
        else:
            print(f"  [Warn] No one-day data for:      {symbol}")


# ---------------------------------------------------------------------------
# Phase II — Matrix Engineering
# ---------------------------------------------------------------------------

def run_phase2(symbols: list[str]):
    print("\n[Phase II] Matrix Engineering")
    build_matrices(symbols)


# ---------------------------------------------------------------------------
# Phase III — Vectorized Backtesting
# ---------------------------------------------------------------------------

def run_phase3(settings: dict):
    print("\n[Phase III] Vectorized Backtesting")

    matrix_dir = ROOT / "data" / "matrix"
    price      = pd.read_parquet(matrix_dir / "price_matrix.parquet")
    volume     = pd.read_parquet(matrix_dir / "volume_matrix.parquet")
    chip_slope = pd.read_parquet(matrix_dir / "chip_matrix.parquet")
    atr        = pd.read_parquet(matrix_dir / "atr_matrix.parquet")

    initial_capital    = settings["initial_capital"]
    partition          = settings["partition"]
    volume_multiplier  = settings["volume_multiplier"]
    concentration_slope = settings["concentration_slope"]
    atr_multiplier     = settings["atr_multiplier"]
    back_test_period   = settings["back_test_period"]

    # Trim to backtest window
    cutoff = pd.Timestamp.today() - pd.DateOffset(years=back_test_period)
    price      = price[price.index >= cutoff]
    volume     = volume[volume.index >= cutoff]
    chip_slope = chip_slope[chip_slope.index >= cutoff]
    atr        = atr[atr.index >= cutoff]

    # Align on common tickers
    common = (
        price.columns
        .intersection(volume.columns)
        .intersection(chip_slope.columns)
        .intersection(atr.columns)
    )
    price      = price[common]
    volume     = volume[common]
    chip_slope = chip_slope[common]
    atr        = atr[common]

    # Signal generation: (Volume > MA20 * multiplier) & (Chip Slope > threshold)
    vol_ma20 = volume.rolling(20).mean()
    entries  = (volume > vol_ma20 * volume_multiplier) & (chip_slope > concentration_slope)

    # Trailing stop: ATR-based fraction of price
    sl_stop = (atr * atr_multiplier) / price

    # Run strategy portfolio
    pf = vbt.Portfolio.from_signals(
        close=price,
        entries=entries,
        sl_stop=sl_stop,
        sl_trail=True,
        init_cash=initial_capital,
        cash_sharing=True,
        group_by=True,
        # min_size= 1000,
        size= 1 / partition,
        size_type="percent",
        # size=initial_capital / partition,
        # size_type="value",
        fees=0.00235,
        # fixed_fees=20,
        slippage=0.001,
        freq="D",
    )

    # Benchmark: 0050.TW buy-and-hold
    bm_close = price.get("0050.TW")
    if bm_close is None:
        bm_raw = yf.download("0050.TW", start=cutoff.strftime("%Y-%m-%d"), auto_adjust=True)
        if not bm_raw.empty:
            bm_close = bm_raw["Close"].squeeze()

    # Phase IV — Reporting & Archiving
    _report(pf, bm_close, initial_capital)

    return pf


# ---------------------------------------------------------------------------
# Phase IV — Reporting & Archiving
# ---------------------------------------------------------------------------

def _report(pf: vbt.Portfolio, benchmark_close, initial_capital: float):
    # Setting export trade log option
    dist_dir = ROOT / "dist"
    dist_dir.mkdir(exist_ok=True)
    # timestamp = datetime.now().strftime("%m_%d_%y_%H%M")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    
    log_path = dist_dir / f"backtest_{timestamp}.log"
    csv_path = dist_dir / f"backtest_{timestamp}.csv"
    
    with open(log_path, "w", encoding="utf-8") as f:
        # 暫時將 stdout (標準輸出) 導向到 Tee 類別
        original_stdout = sys.stdout
        sys.stdout = Tee(sys.stdout, f)
        
        try:
            print("\n" + "=" * 55)
            print("STRATEGY PERFORMANCE")
            print("=" * 55)
            stats = pf.stats()
            print(stats.to_string())

            if benchmark_close is not None and not benchmark_close.empty:
                bm_pf = vbt.Portfolio.from_holding(benchmark_close, init_cash=initial_capital)
                bm_stats = bm_pf.stats(settings=dict(freq="D"))

                print("\n" + "=" * 55)
                print("BENCHMARK  0050.TW  Buy & Hold")
                print("=" * 55)
                print(bm_stats.to_string())

                s_ret = stats.get("Total Return [%]", float("nan"))
                b_ret = bm_stats.get("Total Return [%]", float("nan"))
                print(f"\nStrategy Total Return : {s_ret:.2f}%")
                print(f"Benchmark Total Return: {b_ret:.2f}%")
                print(f"Alpha                 : {s_ret - b_ret:.2f}%")

            pf.trades.records_readable.to_csv(csv_path, index=False)
            print(f"\n[Phase IV] Trade log saved → {csv_path}")
            
        finally:
            # 務必還原 stdout，避免影響後續的其他程式碼
            sys.stdout = original_stdout


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    settings = load_settings()
    update_stock_list()
    symbols  = load_symbols()
    print(f"Loaded {len(symbols)} symbol(s) from stock_list.csv")

    run_phase1(symbols, settings)
    run_phase2(symbols)
    run_phase3(settings)


if __name__ == "__main__":
    main()
