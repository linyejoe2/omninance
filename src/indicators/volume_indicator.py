from .base_indicator import BaseIndicator

import pandas as pd
import numpy as np

class VolumeIndicator(BaseIndicator):
    def __init__(self, symbol: str, period=5):
        super().__init__("成交量動能", symbol=symbol, color="#73c0de")
        self.period = period
        # UI 儀表板範圍：0% 代表無量，200% 代表倍量
        self.min_val = 0.0
        self.max_val = 200.0
        self.price_change = []

    def compute_series(self):
        # 計算 5 日移動平均量 (MAV)
        mav = self.stock_data['Volume'].rolling(window=self.period).mean()
        
        # 3. 定義方向（價量配合）
        # 計算當日漲跌百分比
        self.price_change = self.stock_data['Close'].pct_change()
        
        # 計算成交量佔比: (當前量 / 均量) * 100
        # 如果大於 100 代表放量，小於 100 代表縮量
        vol_ratio = (self.stock_data['Volume'] / mav) * 100

        self.ind_data["Volume"] = mav
        self.ind_data["MAV"] = mav
        self.ind_data["vol_ratio"] = vol_ratio


    def compute_score(self):
        # 方向判定邏輯：
        # 漲且量增 -> 正分
        # 跌且量增 -> 負分 (恐慌)
        # 漲且量縮 -> 分數遞減 (背離)
        # 跌且量縮 -> 分數趨向 0 (洗盤)
        direction = np.where(self.price_change > 0, 1, -1)
        
        # 4. 最終合成評分
        # 基本分 = 方向 * 量能強度
        vol_score = direction * self.ind_data["vol_ratio"]
        
        # 5. 平滑處理 (選用，避免分數跳動太快)
        vol_score_smoothed = vol_score.rolling(window=3).mean()
        
        # vol_score_smoothed.to_csv("./test.csv", index=False)
        
        self.scores = vol_score_smoothed.fillna(0)