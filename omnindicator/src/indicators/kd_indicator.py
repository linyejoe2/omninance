import pandas_ta as ta
import pandas as pd

from .base_indicator import BaseIndicator

class KDIndicator(BaseIndicator):
    def __init__(self, symbol: str, length=9, signal=3):
        super().__init__(name="KD", symbol=symbol, min_val=0, max_val=100, color="#91cc75")
        self.length = length
        self.signal = signal

    def compute_series(self):
        ema = self.stock_data['Close'].ewm(span=self.length, adjust=False).mean()
        self.second_line = ema
        self.second_line_name = "EMA"
        
        # 使用 pandas_ta 快速計算
        # https://www.pandas-ta.dev/api/momentum/#src.pandas_ta.momentum.kdj.kdj
        kdj = ta.kdj(self.stock_data['High'], self.stock_data['Low'], self.stock_data['Close'], length=self.length, signal=self.signal)
        
        self.ind_data["K"] = kdj.iloc[:, 0]
        self.ind_data["D"] = kdj.iloc[:, 1]
        # self.ind_data["J"] = kdj.iloc[:, 2]

    def compute_score(self):
        """
        分數區間,市場狀態,解讀
        80 ~ 100,低檔金叉,KD 位於 20 以下且 K 線強勢穿過 D 線（極佳買點）。
        30 ~ 80,多頭攻擊,KD 處於中位數且持續向上擴散。
        -30 ~ 30,盤整/糾結,K 線與 D 線高度重疊，無明顯趨勢。
        -80 ~ -30,空頭下探,KD 處於高位往下掉，或是正處於跌勢中。
        -100 ~ -80,高檔死叉,KD 位於 80 以上且 K 線由上往下跌破 D 線（危險賣點）。
        """
        # 取得 K 線與 D 線 (注意欄位名稱可能隨參數改變)
        k_line = self.ind_data["K"]
        d_line = self.ind_data["D"]
        
        # --- 部分 A: 位階評分 (佔 50 分) ---
        # 邏輯：50 是中點，低於 20 給高分，高於 80 給低分
        # 公式：(50 - K線) * 1.0 (映射到 -50 ~ 50)
        level_score = (50 - k_line)
        
        # --- 部分 B: 交叉動能評分 (佔 50 分) ---
        # 邏輯：K-D 差值越大，代表動能越強
        # 我們將 K-D 差值限制在 [-15, 15] 之間並放大
        diff = (k_line - d_line) * 3.33  # 15 * 3.33 = 50
        momentum_score = diff.clip(-50, 50)
        
        # --- 最終合成 ---
        final_score = level_score + momentum_score
        self.scores = final_score.clip(-100, 100).fillna(0)