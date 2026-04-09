import pandas_ta as ta
import pandas as pd
import numpy as np

from .base_indicator import BaseIndicator

class MACDIndicator(BaseIndicator):
    def __init__(self, symbol: str, fast=12, slow=26, signal=9):
        super().__init__("MACD", symbol=symbol, color="#5470c6")
        self.fast = fast
        self.slow = slow
        self.signal = signal
        # MACD 柱狀體通常在台股小型股波動較大，大型股較小
        self.min_val = -2.0
        self.max_val = 2.0
        self.macd_df = None
        

    def compute_series(self):      
        
        macd_df = ta.macd(self.stock_data['Close'], fast=self.fast, slow=self.slow, signal=self.signal)
        self.ind_data["MACD"] = macd_df.iloc[:, 0]
        self.ind_data["Signal"] = macd_df.iloc[:, 1]
        
        self.calculate_macd_score(macd_df)
    
    def calculate_macd_score(self, df):
        # 取得 MACD 指標 (假設欄位名稱為 MACD_12_26_9 等)
        # macd: 快線與慢線差, signal: 訊號線, hist: 柱狀圖
        macd = df.iloc[:, 0]
        signal = df.iloc[:, 1]
        hist = df.iloc[:, 2]
        
        self.min_val = macd.min()
        self.max_val = macd.max() 

        # --- 步驟 A: 計算趨勢基礎分 (-60 ~ 60) ---
        # 簡單判定：MACD 在 Signal 之上給正分，之下給負分
        trend_score = np.where(macd > signal, 60, -60)

        # --- 步驟 B: 計算動能加權 (-40 ~ 40) ---
        # 使用近 20 天的柱狀圖絕對值最大值來做標準化，避免不同標的數值差異太大
        lookback = 20
        rolling_max = hist.abs().rolling(window=lookback).max()
        
        # 計算目前柱狀圖在區間中的相對強度 (0 ~ 1)
        # 若 hist 為正且上升，給予正強勢；若 hist 為負且下降，給予負強勢
        momentum_ratio = hist / rolling_max
        momentum_score = momentum_ratio * 40

        # --- 步驟 C: 總分加總 ---
        final_score = trend_score + momentum_score
        
        # 限制邊界在 -100 ~ 100
        self.scores = np.clip(final_score, -100, 100).fillna(0)

    def compute_score(self):
        return