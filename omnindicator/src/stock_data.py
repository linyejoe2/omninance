import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from db import db

def fetch_stock_data(ticker):
    table_name = ticker.replace(".", "_")
    local_data = db.load_data(table_name)
    
    if local_data is not None and not local_data.empty:
        last_date = local_data.index[-1]
        # 檢查是否需要更新 (若最後一筆資料早於昨日)
        if last_date.date() < (datetime.now() - timedelta(days=1)).date():
            print(f"Updating data for {ticker} from {last_date} to {datetime.now()}...")
            start_date = (last_date + timedelta(days=1)).strftime("%Y-%m-%d")
            new_data = download_from_source(ticker, start=start_date)
            
            if not new_data.empty:
                db.save_data(table_name, new_data, if_exists="append")
                return pd.concat([local_data, new_data])
        
        return local_data
    
    # 完全沒資料，抓取最近兩年
    df = download_from_source(ticker, period="2y")
    if not df.empty:
        db.save_data(table_name, df, if_exists="replace")
    return df

def download_from_source(ticker, period=None, start=None):
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