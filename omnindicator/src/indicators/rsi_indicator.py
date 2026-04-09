import pandas_ta as ta
import pandas as pd

from .base_indicator import BaseIndicator

class RSIIndicator(BaseIndicator):
    def __init__(self, symbol: str, length=14):
        super().__init__(name="RSI", symbol=symbol, min_val=0, max_val=100, color="#91cc75")
        self.length = length

    def compute_series(self):
        ema = self.stock_data['Close'].ewm(span=self.length, adjust=False).mean()
        self.second_line = ema
        self.second_line_name = "EMA"
        
        # 使用 pandas_ta 快速計算
        self.ind_data["RSI"] = ta.rsi(self.stock_data['Close'], length=self.length)

    def compute_score(self):
        """
        將 RSI 轉換為 -100 ~ 100 的評分
        邏輯：
        - RSI 20 -> 100 分 (強力買進)
        - RSI 50 -> 0 分 (中立)
        - RSI 80 -> -100 分 (強力賣出)
        """
        # 公式：(50 - RSI) * (100 / 30)
        # 50 為中點，30 為半邊擺動區間 (80-50 或 50-20)
        # 限制範圍並平滑處理
        self.scores = ((50 - self.ind_data["RSI"]) * 3.33).clip(-100, 100).fillna(0)