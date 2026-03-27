import pandas_ta as ta
import pandas as pd

from .base_indicator import BaseIndicator
        
class BiasIndicator(BaseIndicator):
    def __init__(self, symbol: str, weight=1.0, period=20):
        super().__init__(name=f"BIAS", weight=weight, min_val=-20.0, max_val=20.0, color="#91cc75", symbol=symbol)
        self.period = period

    def compute_series(self):
        # 計算移動平均線 (SMA)
        sma = self.stock_data['Close'].rolling(window=self.period).mean()
        
        # Bias 公式: ((當前價 - 均線) / 均線) * 100
        bias = (((self.stock_data['Close'] - sma) / sma) * 100).fillna(0)
        
        self.ind_data["SMA"] = sma
        self.ind_data["BIAS"] = bias

    def compute_score(self):
        # 原始範圍 x < -20 < 0 > 20 > y
        # 調整成 y < 100% < 0% > -100% > x (反著看)
        
        self.scores = (self.ind_data["BIAS"] * -5).clip(-100, 100)
