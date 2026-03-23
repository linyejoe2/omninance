import pandas_ta as ta
import pandas as pd

from .base_indicator import BaseIndicator
        
class BiasIndicator(BaseIndicator):
    def __init__(self, weight=1.0, period=20):
        super().__init__(name=f"BIAS-{period}", weight=weight, min_val=-20.0, max_val=20.0, color="#91cc75")
        self.period = period

    def compute_series(self, df):
        # 計算移動平均線 (SMA)
        sma = df['Close'].rolling(window=self.period).mean()
        # Bias 公式: ((當前價 - 均線) / 均線) * 100
        bias_series = ((df['Close'] - sma) / sma) * 100
        return bias_series.fillna(0)

    def compute_score(self, series):
        # 原始範圍 x < -20 < 0 > 20 > y
        # 調整成 y < 100% < 0% > -100% > x (反著看)
        
        return (series * -5).clip(-100, 100)
        
        scores = pd.Series(0, index=series.index)
        
        # 評分邏輯 (以 10 日 Bias 為例)
        # 超跌 (看多): 當 Bias 低於 -5% 給 +1 分
        scores[series < -5.0] = 1
        
        # 過熱 (看空): 當 Bias 高於 +5% 給 -1 分
        scores[series > 5.0] = -1
        return scores
