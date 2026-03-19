import pandas as pd
from indicators import BaseIndicator
from db import db
import numpy as np

class LargeHolderIndicator(BaseIndicator):
    def __init__(self, weight=1.0, symbol='2330.TW'):
        # 比例通常在 40% - 90% 之間
        super().__init__(name="大戶籌碼", weight=weight, min_val=-100.0, max_val=100.0, color="#8da0cb")
        self.symbol = symbol

    def compute_series(self, _: pd.DataFrame) -> pd.Series:        
        df =  db.get_stock_holder_history(self.symbol)
        
        
        
        return df["continuous_count"]

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