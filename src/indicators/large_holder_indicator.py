import pandas as pd
from indicators import BaseIndicator
from db import db
import numpy as np

class LargeHolderIndicator(BaseIndicator):
    def __init__(self, weight=1.0, symbol='2330.TW', rolling_period=3, linreg_period=8):
        # 比例通常在 40% - 90% 之間
        super().__init__(name="大戶籌碼", weight=weight, min_val=-100.0, max_val=100.0, color="#8da0cb")
        self.symbol = symbol
        self.rolling_period = rolling_period
        self.linreg_period = linreg_period

    def compute_series(self, df: pd.DataFrame) -> pd.Series:        
        stock_holder_history = db.get_stock_holder_history(self.symbol)
        if stock_holder_history.empty:
            return pd.Series(0, index=df.index)
        
        # 2. 統一日期格式
        # 確保主表 df 的 Date 是 datetime
        price_df = df.reset_index()
        price_df['Date'] = pd.to_datetime(price_df.index)
        
        # 轉換籌碼表的 Date (20251003 -> datetime)
        holder_df = stock_holder_history.copy()
        holder_df['Date'] = pd.to_datetime(holder_df['Date'], format='%Y%m%d')

        # 3. 排序 (merge_asof 要求雙方必須依時間排序)
        price_df = price_df.sort_values('Date2')
        holder_df = holder_df.sort_values('Date')

        # 4. 核心對齊：將籌碼資料併入價格表
        # direction='backward' 意思是：對價格表的每個日期，找「該日期或之前」最近的一筆籌碼資料
        merged = pd.merge_asof(
            price_df[['Date2']], 
            holder_df[['Date', 'continuous_count']], 
            on='Date', 
            direction='backward'
        )

        # 5. 處理缺失值並回傳序列
        # 最早的價格資料可能在第一筆籌碼資料之前，此時會是 NaN，我們填 0
        return merged['continuous_count'].fillna(0)

    def compute_score(self, series: pd.Series) -> pd.Series:
        """
        籌碼評分邏輯 (線性累積)：
        - 持續增加：一週 +20, 兩週 +40 ... 五週以上 +100
        - 持續減少：一週 -20, 兩週 -40 ... 五週以上 -100
        - 中斷或無變動：0
        - 改成八週最高
        """
        scores = (series * 12.5).clip(-100, 100)
        
        return scores