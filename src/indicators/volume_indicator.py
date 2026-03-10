from .base_indicator import BaseIndicator

import pandas as pd

class VolumeIndicator(BaseIndicator):
    def __init__(self, period=5):
        super().__init__("成交量動能", color="#73c0de")
        self.period = period
        # UI 儀表板範圍：0% 代表無量，200% 代表倍量
        self.min_val = 0.0
        self.max_val = 200.0

    def compute_series(self, df: pd.DataFrame) -> pd.Series:
        # 計算 5 日移動平均量 (MAV)
        mav = df['Volume'].rolling(window=self.period).mean()
        
        # 計算成交量佔比: (當前量 / 均量) * 100
        # 如果大於 100 代表放量，小於 100 代表縮量
        vol_ratio = (df['Volume'] / mav) * 100
        return vol_ratio.fillna(100)

    def compute_score(self, series: pd.Series) -> pd.Series:
        scores = pd.Series(0, index=series.index)
        
        # 評分邏輯：
        # 1. 顯著放量 (大於均量 1.5 倍): 給 +1 分 (代表攻擊動能)
        scores[series > 150] = 1
        
        # 2. 極度萎縮 (小於均量 0.5 倍): 給 -1 分 (代表市場冷清或出貨完畢)
        scores[series < 50] = -1
        
        return scores