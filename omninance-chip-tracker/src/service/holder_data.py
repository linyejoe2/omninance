from io import StringIO
from pathlib import Path
import time

import pandas as pd
import numpy as np
import pandas_ta as pta
from datetime import datetime
import requests

# ---------------------------------------------------------------------------
# Rate limiting — 10 s minimum between any request to norway.twsthr.info
# ---------------------------------------------------------------------------

_last_twsthr_request: float = 0.0
_TWSTHR_INTERVAL: int = 10


def _throttle():
    global _last_twsthr_request
    wait = _TWSTHR_INTERVAL - (time.time() - _last_twsthr_request)
    if wait > 0:
        time.sleep(wait)
    _last_twsthr_request = time.time()


# ---------------------------------------------------------------------------
# Core scraper
# ---------------------------------------------------------------------------

def sync_stock_holder_data(symbol) -> pd.DataFrame:
        """
        抓取股權分配表
        symbol 格式: 2330.TW -> 需轉為 2330
        """
        stock_code = symbol.split('.')[0]
        url = f"https://norway.twsthr.info/StockHolders.aspx?stock={stock_code}"

        try:
            # 該網站有基本的防爬蟲，需加上 Header
            _throttle()
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = requests.get(url, headers=headers)
            response.encoding = 'utf-8'

            # 解析表格
            dfs = pd.read_html(StringIO(response.text))
            df = dfs[9]
            df = df.iloc[:-2, 2:15].dropna(how='all')
            df.columns = df.iloc[0]
            df = df.iloc[1:].reset_index(drop=True)

            if df is None:
                return pd.DataFrame()

            return df

        except Exception as e:
            print(f"Error fetching holder data for {symbol}: {e}")
            return pd.DataFrame()


# ---------------------------------------------------------------------------
# Incremental update helpers
# ---------------------------------------------------------------------------

def check_newest_date(symbol: str) -> str | None:
    """
    Returns the newest 資料日期 (YYYYMMDD string) currently published on
    twsthr.info.  Result is cached by the caller across symbols to avoid
    repeated requests.
    """
    df = sync_stock_holder_data(symbol)
    if df is None or df.empty:
        return None
    return str(df["資料日期"].iloc[0])


def get_newest_stock_holder_data(save_path: Path) -> None:
    """
    this API will take very long time to fetch (about 10 sec)
    because this data contain all stock data of taiwan
    make sure to store it in ./data/raw/holders/one_day/03_27_26.parquet
    befor use it

    Returns:
        pd.DataFrame: _description_
    """
    import requests
    import pandas as pd

    url='https://smart.tdcc.com.tw/opendata/getOD.ashx?id=1-5'
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    data=pd.read_csv(url, storage_options=headers)
    
    data['證券代號'] = data['證券代號'].astype(str).str.strip()
    
    data.to_parquet(save_path, index=False)


def get_stock_large_holder_percentage(symbol: str, one_day_path: Path) -> pd.Series | None:
    """
    Reads the one-day parquet and returns the row for *symbol* as a
    Series (without the 'symbol' key), ready to prepend to the ㄋㄋ CSV.
    """
    stock_code = symbol.split('.')[0]
    try:
        df = pd.read_parquet(one_day_path)
        match = df[df["證券代號"] == stock_code]
        if match.empty:
            return None
        return _summarize(match)
    except Exception as e:
        print(f"[Holder] Error reading one-day parquet for {symbol}: {e}")
        return None


# ---------------------------------------------------------------------------
# Slope calculation
# ---------------------------------------------------------------------------

def calc_slope(df: pd.DataFrame, rolling_period=3, linreg_period=8) -> pd.Series:
        shdf = df["資料日期"].to_frame(name="Date")

        shdf["400up"] = df[">400張大股東 持有百分比"].apply(pd.to_numeric, errors='coerce')
        shdf["1000up"] = df[">1000張大股東 持有百分比"].apply(pd.to_numeric, errors='coerce')
        shdf["close"] = df["收盤價"].apply(pd.to_numeric, errors='coerce')

        shdf = shdf[::-1].reset_index(drop=True)

        shdf['Date'] = pd.to_datetime(shdf['Date'], format='%Y%m%d').dt.as_unit('ns')

        # 2. calc 400up diff > ma > linear regression > slope
        diff = shdf["400up"].diff().fillna(0)
        diff_rolling = diff.rolling(window=rolling_period).mean().fillna(0)
        diff_lenreg_slope = pta.linreg(diff_rolling, linreg_period, slope=True).bfill()

        return diff_lenreg_slope


def _summarize(df):
    # 第1級至第15級，係持股為1-999 、1,000-5,000、5,001-10,000、10,001-15,000、15,001-20,000、
    # 20,001-30,000、30,001-40,000、40,001-50,000、50,001-100,000、100,001-200,000、
    # 200,001-400,000、400,001-600,000、600,001-800,000、800,001-1,000,000、1,000,001以上等15個級距。
    date = df['資料日期'].iloc[0]
    # date = datetime.strptime(str(df['資料日期'].iloc[0]), "%Y%m%d").date()

    
    # 2. 定義「大股東」範圍 (8-15 級對應 400張以上至 1000張以上)
    # 註：15級通常是 1000張以上，8級是 400-600張
    up400_holder_mask = df['持股分級'].between(12, 15)
    
    # 3. 定義「總計行」(第 17 級)
    total_row = df[df['持股分級'] == 17].iloc[0]
    
    # 4. 計算大股東統計量
    up400_holders = df[up400_holder_mask]
    up400_shares = up400_holders['股數'].sum()
    up400_pct = up400_holders['占集保庫存數比例%'].sum()
    up400_count = up400_holders['人數'].sum()

    
    # 5. 提取總計資訊
    total_shares = total_row['股數']
    total_people = total_row['人數']
    
    # 6. 封裝結果 (1張 = 1000股)
    summary = {
        "資料日期": date,
        "集保總張數": int((total_shares / 1000).round(0)),
        "總股東 人數": total_people,
        "平均張數/人": ((total_shares / 1000) / total_people if total_people > 0 else 0).round(2),
        ">400張大股東 持有張數": int((up400_shares / 1000).round(0)),
        ">400張大股東 持有百分比": up400_pct,
        ">400張大股東 人數": up400_count,
        "400~600張人數": df.iloc[11]['人數'],
        "600~800張人數": df.iloc[12]['人數'],
        "800~1000張人數": df.iloc[13]['人數'],
        ">1000張人數": df.iloc[14]['人數'],
        ">1000張大股東 持有百分比": df.iloc[14]['占集保庫存數比例%'],
        "收盤價": "0"
    }
    
    return pd.Series(summary)