import pandas as pd
from indicators import BaseIndicator
from db import db

class BusinessCycleIndicator(BaseIndicator):
    def __init__(self, symbol: str):
        super().__init__(name="景氣燈號", symbol= symbol, min_val=9.0, max_val=45.0, color="#FF4B4B")

    def compute_series(self):
        """獲取燈號分數並對齊股票交易日"""
        # 1. 從資料庫讀取月度分數
        monthly_scores = db._get_all_business_indicators()
        
        if monthly_scores.empty:
            return pd.Series(0.0, index=self.stock_data.index)

        # 2. 對齊與填充：將月資料轉為日資料
        # 我們先建立一個包含股票所有日期的空 Series，然後填充
        daily_scores = monthly_scores.reindex(self.stock_data.index, method='ffill')
        
        # 處理資料夾縫：如果股票日期早於燈號起始日，補上最小值 9
        self.ind_data["scores"] = daily_scores.fillna(9)

    def compute_score(self):
        # %B 原始範圍是 9 < x > 45
        # 調整成 -100% < x > 100%
        
        self.scores =  round((self.ind_data["scores"] - 27) * -5.56, 2).clip(-100, 100)