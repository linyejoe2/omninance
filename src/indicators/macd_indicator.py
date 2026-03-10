import pandas_ta as ta
import pandas as pd

from .base_indicator import BaseIndicator

class MACDIndicator(BaseIndicator):
    def __init__(self, fast=12, slow=26, signal=9):
        super().__init__("MACD 趨勢指標", color="#5470c6")
        self.fast = fast
        self.slow = slow
        self.signal = signal
        # MACD 柱狀體通常在台股小型股波動較大，大型股較小
        self.min_val = -2.0
        self.max_val = 2.0

    def compute_series(self, df: pd.DataFrame) -> pd.Series:
        # pandas_ta 傳回 DataFrame: [MACD, MACD_Signal, MACD_Hist]
        macd_df = ta.macd(df['Close'], fast=self.fast, slow=self.slow, signal=self.signal)
        
        # 我們主要觀察 Histogram (柱狀體)，通常欄位名稱結尾是 _h
        # 例如: MACDh_12_26_9
        hist_col = macd_df.columns[2] 
        return macd_df[hist_col].fillna(0)

    def compute_score(self, series: pd.Series) -> pd.Series:
        scores = pd.Series(0, index=series.index)
        
        # 向量化判定：黃金交叉與死亡交叉
        # 當今日柱狀體 > 0 且昨日 < 0 (或持續增長)
        # 這裡採用最穩健的邏輯：紅柱(正值)給 1 分，綠柱(負值)給 -1 分
        scores[series > 0] = 1
        scores[series < 0] = -1
        
        return scores