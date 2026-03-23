import pandas_ta as ta
import pandas as pd

from .base_indicator import BaseIndicator

class BBIndicator(BaseIndicator):
    def __init__(self, length=20, std=2):
        super().__init__("BBands", color="#fac858")
        self.length = length
        self.std = std

    def compute_series(self, df: pd.DataFrame) -> pd.Series:
        bb = ta.bbands(df['Close'], length=self.length, std=self.std)
        # 計算 %B (Bollinger Band Percent)
        # 公式: (Price - Lower) / (Upper - Lower) * 100
        lower = bb.iloc[:, 0]
        upper = bb.iloc[:, 2]
        pos_series = ((df['Close'] - lower) / (upper - lower)) * 100
        return pos_series.fillna(50) # 處理寬度為 0 的極端情況

    def compute_score(self, series: pd.Series) -> pd.Series:
        # %B 原始範圍是 x < 0% < 50% > 100% > y
        # 調整成 x < -100% < 0% > 100% > y
        return ((series - 50) * 2).clip(-100, 100)
        
        # scores = pd.Series(0, index=series.index)
        # scores[series < 20] = 1   # 觸及下軌，超賣看多
        # scores[series > 80] = -1  # 觸及上軌，超買看空~
        # return scores