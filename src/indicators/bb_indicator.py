import pandas_ta as ta
import pandas as pd

from .base_indicator import BaseIndicator

class BBIndicator(BaseIndicator):
    def __init__(self, symbol: str, length=20, std=2):
        super().__init__("BBands", color="#fac858", symbol=symbol)
        self.length = length
        self.std = std

    def compute_series(self):
        self.bb = ta.bbands(self.stock_data['Close'], length=self.length, std=self.std)
        # 計算 %B (Bollinger Band Percent)
        # 公式: (Price - Lower) / (Upper - Lower) * 100
        self.ind_data["lower_band"] = self.bb.iloc[:, 0]
        self.ind_data["upper_band"] = self.bb.iloc[:, 2]
        self.ind_data["pos_series"] = (((self.stock_data['Close'] - self.ind_data["lower_band"]) / (self.ind_data["upper_band"] - self.ind_data["lower_band"])) * 100).bfill()


    def compute_score(self):
        # %B 原始範圍是 x < 0% < 50% > 100% > y
        # 調整成 x < -100% < 0% > 100% > y
        self.scores =  ((self.ind_data["pos_series"] - 50) * -2).clip(-100, 100)
        
        # scores = pd.Series(0, index=series.index)
        # scores[series < 20] = 1   # 觸及下軌，超賣看多
        # scores[series > 80] = -1  # 觸及上軌，超買看空~
        # return scores