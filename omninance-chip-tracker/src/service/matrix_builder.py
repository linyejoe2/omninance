from pathlib import Path

import pandas as pd
import pandas_ta as pta

from src.service.holder_data import calc_slope
from pandas.tseries.offsets import BDay

ROOT = Path(__file__).parent.parent.parent


def build_matrices(symbols: list[str]):
    raw_tickers = ROOT / "data" / "raw" / "tickers"
    raw_holders = ROOT / "data" / "raw" / "holders"
    matrix_dir = ROOT / "data" / "matrix"
    matrix_dir.mkdir(parents=True, exist_ok=True)

    price_dict: dict = {}
    volume_dict: dict = {}
    atr_dict: dict = {}
    chip_dict: dict = {}

    for symbol in symbols:
        file_key = symbol.replace(".", "_")

        # --- OHLCV ---
        ticker_path = raw_tickers / f"{file_key}.csv"
        if ticker_path.exists():
            df = pd.read_csv(ticker_path, index_col=0, parse_dates=True)
            required = {"Close", "High", "Low", "Volume"}
            if not df.empty and required.issubset(df.columns):
                price_dict[symbol] = df["Close"]
                volume_dict[symbol] = df["Volume"]

                atr_series = pta.atr(df["High"], df["Low"], df["Close"], length=14)
                if atr_series is not None and not atr_series.empty:
                    atr_dict[symbol] = atr_series

        # --- Holder / Chip Slope ---
        holder_path = raw_holders / f"{file_key}_holders.csv"
        if holder_path.exists():
            try:
                df_holder = pd.read_csv(holder_path, encoding="utf-8-sig")
                if df_holder.empty:
                    continue

                # calc_slope reverses rows (oldest → newest); mirror that for dates
                raw_dates = pd.to_datetime(
                    df_holder["資料日期"].astype(str), format="%Y%m%d", errors="coerce"
                )
                dates_asc = raw_dates.iloc[::-1].reset_index(drop=True)

                slope = calc_slope(df_holder)
                if slope is not None and not slope.empty:
                    real_trading_dates = pd.to_datetime(dates_asc.values) + BDay(1)
                    slope_series = pd.Series(slope.values, index=real_trading_dates, name=symbol)
                    chip_dict[symbol] = slope_series.dropna()

            except Exception as e:
                print(f"[Matrix] Skipping holder data for {symbol}: {e}")

    # Build and save Price matrix
    if price_dict:
        price_matrix = pd.DataFrame(price_dict).sort_index()
        price_matrix.to_parquet(matrix_dir / "price_matrix.parquet")
        print(f"[Phase II] price_matrix saved  {price_matrix.shape}")
    else:
        print("[Phase II] No price data — skipping price_matrix")
        return

    # Build and save Volume matrix
    if volume_dict:
        volume_matrix = pd.DataFrame(volume_dict).sort_index()
        volume_matrix.to_parquet(matrix_dir / "volume_matrix.parquet")
        print(f"[Phase II] volume_matrix saved {volume_matrix.shape}")

    # Build and save ATR matrix
    if atr_dict:
        atr_matrix = pd.DataFrame(atr_dict).sort_index()
        atr_matrix.to_parquet(matrix_dir / "atr_matrix.parquet")
        print(f"[Phase II] atr_matrix saved    {atr_matrix.shape}")

    # Build and save Chip Diff Slope matrix (weekly → daily via ffill)
    if chip_dict:
        daily_index = price_matrix.index
        chip_matrix = pd.DataFrame(chip_dict)
        chip_matrix = chip_matrix.reindex(daily_index, method="ffill")
        chip_matrix.sort_index(inplace=True)
        chip_matrix.to_parquet(matrix_dir / "chip_matrix.parquet")
        print(f"[Phase II] chip_matrix saved   {chip_matrix.shape}")
