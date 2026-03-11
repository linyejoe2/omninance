
import pandas as pd
import numpy as np
from indicators import BaseIndicator

class BacktestEngine:
    @staticmethod
    def run(df: pd.DataFrame, indicator_list: list[BaseIndicator], parts, buy_threshold, sell_threshold, initial_capital=100000):
        # 1. 建立分數矩陣
        score_matrix = pd.DataFrame(index=df.index)
        for ind in indicator_list:
            _, score_series = ind.calculate(df)
            score_matrix[ind.name] = score_series
        
        # 計算總分與訊號
        df['total_score'] = score_matrix.sum(axis=1)
        
        # 2. 產生買賣訊號
        df['signal'] = np.nan
        df.loc[df['total_score'] >= buy_threshold, 'signal'] = 1
        df.loc[df['total_score'] <= sell_threshold, 'signal'] = 0
        df['position_signal'] = df['signal'].ffill().fillna(0)
        
        # 3. 資金管理：分幾塊投入 (Position Sizing)
        # 例如分 4 塊，每塊就是 0.25 的權重
        weight_per_part = 1.0 / parts
        df['strategy_weight'] = df['position_signal'] * weight_per_part
        
        # 4. 績效與結餘計算
        df['market_return'] = df['Close'].pct_change().fillna(0)
        
        # 買入持有 (Buy & Hold) 結餘
        df['buy_and_hold_cumulative_return'] = (1 + df['market_return']).cumprod()
        df['buy_and_hold_balance'] = initial_capital * df['buy_and_hold_cumulative_return']
        
        # 策略結餘 (隔日生效避免 Look-ahead bias)
        df['strategy_daily_return'] = (df['strategy_weight'].shift(1) * df['market_return']).fillna(0)
        df['strategy_cumulative_return'] = (1 + df['strategy_daily_return']).cumprod()
        df['strategy_balance'] = initial_capital * df['strategy_cumulative_return']
        
        return df, score_matrix

    @staticmethod
    def calculate_metrics(df):
        """計算關鍵績效指標"""
        final_strategy_return = (df['strategy_cumulative_return'].iloc[-1] - 1) * 100
        final_market_return = (df['buy_and_hold_cumulative_return'].iloc[-1] - 1) * 100
        
        # 最大回撤 (MDD)
        rolling_max = df['strategy_cumulative_return'].cummax()
        drawdown = (df['strategy_cumulative_return'] - rolling_max) / rolling_max
        mdd = drawdown.min() * 100
        
        # 勝率 (以交易次數計)
        # 這裡簡單定義：每日報酬 > 0 為贏
        win_rate = (df[df['strategy_daily_return'] > 0].shape[0] / df[df['strategy_daily_return'] != 0].shape[0]) * 100 if df[df['strategy_daily_return'] != 0].shape[0] > 0 else 0
        
        return {
            "Total Return (%)": f"{final_strategy_return:.2f}%",
            "Market Return (%)": f"{final_market_return:.2f}%",
            "Max Drawdown (%)": f"{mdd:.2f}%",
            "Win Rate (%)": f"{win_rate:.1f}%"
        }