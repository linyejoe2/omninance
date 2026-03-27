from io import StringIO
import sqlite3

import pandas as pd
from indicators import BaseIndicator
from db import db
import numpy as np
import pandas_ta as pta
from datetime import datetime, timedelta
import requests
from util import bounded_cumsum

class LargeHolderIndicator(BaseIndicator):
    def __init__(self, weight=1.0, symbol='2330.TW', rolling_period=3, linreg_period=8):
        """
        Only focus on those holder holding up to 400 share.
        rolling_period (int, optional): period of moving average. Defaults to 3.
        linreg_period (int, optional): period of linear regression. Defaults to 8.
        """
        # 比例通常在 40% - 90% 之間
        super().__init__(name="大戶籌碼", weight=weight, min_val=-100.0, max_val=100.0, color="#8da0cb")
        self.symbol = symbol
        self.rolling_period = rolling_period
        self.linreg_period = linreg_period

    def get_stock_holder_history(self, symbol) -> pd.DataFrame:
        stock_code = symbol.split('.')[0]
        table_name = f"stock_holders_{stock_code}"
        today = datetime.now().strftime('%Y-%m-%d')
        need_sync = False

        with sqlite3.connect(db.db_name) as conn:
            cursor = conn.cursor()

            cursor.execute("SELECT last_check_date FROM sync_log WHERE stock_code=?", (stock_code,))
            row = cursor.fetchone()

            if row and row[0] == today:
                print(f"{stock_code} 今日已檢查過，跳過同步")
                return pd.read_sql(f"SELECT * FROM {table_name} ORDER BY Date ASC", conn)

            cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'")
            if not cursor.fetchone():
                need_sync = True
            else:
                try:
                    cursor.execute(f"SELECT MAX(Date) FROM {table_name}")
                    last_date_str = cursor.fetchone()[0]
                    if last_date_str:
                        last_date = datetime.strptime(str(last_date_str), '%Y%m%d')
                        if (datetime.now() - last_date) > timedelta(days=5):
                            need_sync = True
                    else:
                        need_sync = True
                except Exception as e:
                    print(f"檢查日期時發生錯誤: {e}")
                    need_sync = True

        if need_sync:
            print(f"初始化大戶持股資料: {symbol}")
            success, message = self.sync_stock_holder_data(symbol)
            if not success:
                print(f"初始化同步失敗: {message}")
                return pd.DataFrame()

        try:
            with sqlite3.connect(db.db_name) as conn:
                return pd.read_sql(f"SELECT * FROM {table_name} ORDER BY Date ASC", conn)
        except Exception as e:
            print(f"Error fetching holder history: {e}")
            return pd.DataFrame()

    def compute_series(self, df: pd.DataFrame) -> pd.Series:
        # 1. Get stock holder history
        stock_holder_history = self.get_stock_holder_history(self.symbol)
        if stock_holder_history.empty:
            return pd.Series(0, index=df.index)
        
        
        # 3. scale data to match df
        scaled = self._scale_to_day(df, stock_holder_history)
        return scaled["refined_score"].fillna(0)

    def compute_score(self, series: pd.Series) -> pd.Series:
        """
        籌碼評分邏輯 (線性累積)：
        - 持續增加：一週 +20, 兩週 +40 ... 五週以上 +100
        - 持續減少：一週 -20, 兩週 -40 ... 五週以上 -100
        - 中斷或無變動：0
        - 改成八週最高
        """
        return series
    
    def _scale_to_day(self, df, holder_df):
        # 確保輸入的 df 有 Date 欄位可以對齊，或者從 Index 提取
        temp_df = df.copy()
        temp_df = temp_df.reset_index()

        temp_df['Date'] = pd.to_datetime(temp_df['Date']).dt.as_unit('ns')
        holder_df["Date"] = pd.to_datetime(holder_df["Date"]).dt.as_unit('ns')
        
        # 使用 merge_asof 進行前向填充對齊
        merged = pd.merge_asof(
            temp_df[['Date']], 
            holder_df[['Date', 'refined_score']], 
            on='Date', 
            direction='backward'
        )
        return merged
    
    def sync_stock_holder_data(self, symbol):
        """
        抓取股權分配表
        symbol 格式: 2330.TW -> 需轉為 2330
        """
        stock_code = symbol.split('.')[0]
        url = f"https://norway.twsthr.info/StockHolders.aspx?stock={stock_code}"
        today = datetime.now().strftime('%Y-%m-%d')
        
        try:
            # 該網站有基本的防爬蟲，需加上 Header
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = requests.get(url, headers=headers)
            response.encoding = 'utf-8'
            
            # 解析表格
            dfs = pd.read_html(StringIO(response.text))
            df = dfs[9]
            df = df.iloc[:-2, 2:15].dropna(how='all')
            df.columns = df.iloc[0]
            df = df.iloc[1:].reset_index(drop=True)
            
            if df is None: return False, "找不到股權表格"
            
            # 直接計算總分
            
            shdf = df["資料日期"].to_frame( name="Date")

            shdf["400up"] = df[">400張大股東 持有百分比"].apply(pd.to_numeric, errors='coerce')
            shdf["1000up"] =  df[">1000張大股東 持有百分比"].apply(pd.to_numeric, errors='coerce')
            shdf["close"] =  df["收盤價"].apply(pd.to_numeric, errors='coerce')

            shdf = shdf[::-1].reset_index(drop=True)

            shdf['Date'] = pd.to_datetime(shdf['Date'], format='%Y%m%d').dt.as_unit('ns')
            
            # 2. calc 400up diff > ma > linear regression > slope
            diff = shdf["400up"].diff().fillna(0)
            diff_rolling = diff.rolling(window=self.rolling_period).mean().fillna(0)
            diff_lenreg_slope = pta.linreg(diff_rolling, self.linreg_period, slope=True).bfill()

            # 3. scale slope to score -100 ~ 100
            rolling_std = diff_lenreg_slope.rolling(window=self.linreg_period*4).std().bfill()
            shdf["refined_score"] = (diff_lenreg_slope / rolling_std * 50).clip(-100, 100)

            
            # 存入資料庫
            db.save_data(f"stock_holders_{stock_code}", shdf)
            db.update_sync_log(stock_code, today)
            return True, f"同步成功: {len(shdf)} 筆資料"

        except Exception as e:
            return False, f"爬取失敗: {e}"