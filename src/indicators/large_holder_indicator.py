import pandas as pd
from indicators import BaseIndicator
from db import db
import numpy as np

class LargeHolderIndicator(BaseIndicator):
    def __init__(self, weight=1.0, symbol='2330.TW'):
        # 比例通常在 40% - 90% 之間
        super().__init__(name="大戶籌碼", weight=weight, min_val=0.0, max_val=100.0, color="#8da0cb")
        self.symbol = symbol

    def compute_series(self, _: pd.DataFrame) -> pd.Series:        
        df =  db.get_stock_holder_history(self.symbol)
        
        df["400up"] = df["400 ~600"].apply(pd.to_numeric, errors='coerce') + df["600 ~800"].apply(pd.to_numeric, errors='coerce') + df["800 ~1000"].apply(pd.to_numeric, errors='coerce') + df["1000張 以上"].apply(pd.to_numeric, errors='coerce')
        
        return df["400up"].round(2)

    def compute_score(self, series: pd.Series) -> pd.Series:
        """
        籌碼評分邏輯 (線性累積)：
        - 持續增加：一天 +20, 兩天 +40 ... 五天以上 +100
        - 持續減少：一天 -20, 兩天 -40 ... 五天以上 -100
        - 中斷或無變動：0
        """
        # 1. 計算每日變動方向：正為 1, 負為 -1, 無變動為 0
        diff = series.diff()
        direction = np.sign(diff).fillna(0)

        # 2. 計算連續相同方向的天數
        # 透過比對當前與前一筆是否相同，來建立「區塊 ID」
        group = (direction != direction.shift()).cumsum()
        
        # 在每個區塊內進行累計計數
        # direction * (加上一個計數序列)
        continuous_days = direction.groupby(group).cumcount() + 1
        
        # 修正：如果方向是 0 (無變動)，天數應該也是 0
        continuous_count = continuous_days * direction
        
        # 3. 轉換為分數：天數 * 20，並限制在 [-100, 100] 之間
        scores = (continuous_count * 20).clip(-100, 100)
        
        return scores