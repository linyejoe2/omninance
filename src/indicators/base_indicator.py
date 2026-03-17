from abc import ABC, abstractmethod
import pandas as pd

class BaseIndicator(ABC):
    def __init__(self, name, weight=1.0, min_val=0.0, max_val=100.0, color="#5470c6"):
        self.name = name
        self.weight = weight
        self.min_val = min_val
        self.max_val = max_val
        self.color = color
        
        # 存儲最後一筆的狀態 (用於儀表板)
        self.current_value = 0.0
        self.score = 0 

    @abstractmethod
    def compute_series(self, df: pd.DataFrame) -> pd.Series:
        """計算指標的原始數值序列 (如 RSI 曲線)"""
        pass

    @abstractmethod
    def compute_score(self, series: pd.Series) -> pd.Series:
        """根據指標數值，轉換為多空評分序列 (-100, 0, 100)"""
        pass

    def calculate(self, df: pd.DataFrame):
        """整合計算，並更新當前狀態"""
        # 1. 計算數值與分數序列
        val_series = self.compute_series(df)
        score_series = self.compute_score(val_series)
        
        # 2. 更新當前實例屬性 (給 Streamlit 儀表板使用)
        self.current_value = float(val_series.iloc[-1])
        self.score = int(score_series.iloc[-1])
        
        # 3. 回傳完整序列 (給回測引擎使用)
        return val_series, score_series