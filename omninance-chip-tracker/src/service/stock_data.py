import yfinance as yf
import pandas as pd

def download_tickers(ticker, period="5y", start=None):
    """封裝 yfinance 抓取與清洗邏輯"""
    try:
        df = yf.download(ticker, period=period, start=start, auto_adjust=True)
        if df.empty:
            return pd.DataFrame()

        # 處理 MultiIndex 欄位
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df.columns = df.columns.astype(str)
        return df
    except Exception as e:
        print(f"Error downloading {ticker}: {e}")
        return pd.DataFrame()
