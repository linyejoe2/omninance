import pandas_ta as ta
import pandas as pd

from .base_indicator import BaseIndicator

class RSIIndicator(BaseIndicator):
    def __init__(self, length=14):
        super().__init__(name="RSI", min_val=0, max_val=100, color="#91cc75")
        self.length = length

    def compute_series(self, df):
        # 使用 pandas_ta 快速計算
        return ta.rsi(df['Close'], length=self.length)

    def compute_score(self, series):
        scores = pd.Series(0, index=series.index)
        scores[series < 30] = 1   # 超賣，看多
        scores[series > 70] = -1  # 超買，看空
        return scores