import pandas_ta as ta
import pandas as pd
from stock_data import fetch_stock_data

from .base_indicator import BaseIndicator

class VIXIndicator(BaseIndicator):
    def __init__(self, symbol: str, lookback=252):
        super().__init__(name="VIX", symbol=symbol, min_val=0, max_val=60, color="#91cc75")
        self.lookback = lookback

    def compute_series(self):
        vix = fetch_stock_data("^VIX")
        aligned_vix = self._align_vix_to_taiwan(self.stock_data, vix)
        # vix_rank = aligned_vix["Close"].rolling(window=self.lookback).apply(
        #     lambda x: (x.iloc[-1] - x.min()) / (x.max() - x.min() + 1e-9)
        # ) * 100
        
        self.ind_data["VIX"] = aligned_vix["Close"]
        # self.ind_data["VIX Rank"] = vix_rank.fillna(50)
        # self.ind_data.to_csv("./test.csv", index=False)

    def compute_score(self):
        """
        將 VIX 轉換為 -100 ~ 100 的評分
        邏輯：
        - VIX 20 -> 100 分 (強力買進)
        - VIX 50 -> 0 分 (中立)
        - VIX 80 -> -100 分 (強力賣出)
        """
        # 公式：(50 - VIX) * (100 / 30)
        # 50 為中點，30 為半邊擺動區間 (80-50 或 50-20)
        # 限制範圍並平滑處理
        self.scores = ((self.ind_data["VIX"] - 50) * 2).clip(-100, 100).fillna(0)
        
    def _align_vix_to_taiwan(self, stock_df, vix_df):
        """
        stock_df: 包含 ['Date', 'Close'] 的台股日線
        vix_df: 包含 ['Date', 'Close'] 的 ^VIX 日線
        """
        stock_df_copy = stock_df.copy()
        stock_df_copy = stock_df_copy.reset_index()
        vix_df_copy = vix_df.copy()
        vix_df_copy = vix_df_copy.reset_index()
        
        # --- 步驟 1: 強制轉換時間格式與單位 [ns] ---
        # 確保兩者都是 Datetime 物件且單位一致
        stock_df_copy['Date'] = pd.to_datetime(stock_df_copy['Date']).dt.as_unit('ns')
        vix_df_copy['Date'] = pd.to_datetime(vix_df_copy['Date']).dt.as_unit('ns')

        # --- 步驟 2: 排序 (merge_asof 要求 Key 必須排序) ---
        stock_df_copy = stock_df_copy.sort_values("Date")
        vix_df_copy = vix_df_copy.sort_values("Date")

        # --- 步驟 3: 合併與對齊 ---
        # 我們只取 VIX 的收盤價，並更名為 'vix_raw'
        aligned = pd.merge_asof(
            stock_df_copy[['Date']], 
            vix_df_copy[['Date', 'Close']],
            on='Date',
            direction='backward'
        )

        # --- 步驟 4: 處理 NaN (開頭沒資料的部分) ---
        # 使用 bfill 填補最早期的空白，或者直接 fillna(20) 給一個中性的 VIX 值
        aligned['Close'] = aligned['Close'].ffill().bfill()

        return aligned