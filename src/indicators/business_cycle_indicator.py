import pandas as pd
from indicators import BaseIndicator
from db import db

class BusinessCycleIndicator(BaseIndicator):
    def __init__(self):
        super().__init__(name="景氣燈號", min_val=9.0, max_val=45.0, color="#FF4B4B")
        self.database = db

    def compute_series(self, data_frame: pd.DataFrame) -> pd.Series:
        """獲取燈號分數並對齊股票交易日"""
        # 1. 從資料庫讀取月度分數
        monthly_scores = self.database._get_all_business_indicators()
        
        if monthly_scores.empty:
            return pd.Series(0.0, index=data_frame.index)

        # 2. 對齊與填充：將月資料轉為日資料
        # 我們先建立一個包含股票所有日期的空 Series，然後填充
        daily_scores = monthly_scores.reindex(data_frame.index, method='ffill')
        
        # 處理資料夾縫：如果股票日期早於燈號起始日，補上最小值 9
        return daily_scores.fillna(9.0)

    def compute_score(self, series: pd.Series) -> pd.Series:
        """根據分數區間轉換為多空評分"""
        indicator_score = pd.Series(0, index=series.index)
        
        # 藍燈 (衰退): 9-16 分
        indicator_score[series <= 16] = -1
        
        # 綠燈 (穩定) 至 黃紅燈 (趨熱): 23-37 分
        # 這段區間通常是股市的多頭強勢期
        indicator_score[(series >= 23) & (series <= 37)] = 1
        
        # 紅燈 (過熱): 38-45 分
        # 實務上紅燈出現時股價往往已高，此處給予 0 分或 0.5 分以示警戒，不宜追多
        indicator_score[series >= 38] = 0
        
        return indicator_score