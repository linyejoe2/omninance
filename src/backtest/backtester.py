
import pandas as pd
import numpy as np
from numba import jit
from indicators import BaseIndicator

@jit(nopython=True)
def bounded_cumsum(signals, lower_bound=0, upper_bound=4):
    n = len(signals)
    result = np.zeros(n)
    current_val = 0.0
    
    for i in range(n):
        # 核心邏輯：先相加，立即限制邊界，再作為下一次的基礎
        current_val = current_val + signals[i]
        if current_val > upper_bound:
            current_val = upper_bound
        elif current_val < lower_bound:
            current_val = lower_bound
        result[i] = current_val
        
    return result

class BacktestEngine:
    @staticmethod
    def run(df: pd.DataFrame, indicator_list: list[BaseIndicator], parts, buy_threshold, sell_threshold, initial_capital=100000):
        # 1. 建立分數矩陣
        score_matrix = pd.DataFrame(index=df.index)
        for ind in indicator_list:
            _, score_series = ind.calculate(df)
            weighted_score = score_series * ind.weight
            score_matrix[ind.name] = weighted_score
        
        # 計算總分與訊號
        df['total_score'] = score_matrix.sum(axis=1) / len(indicator_list)
        
        # 2. 產生買賣訊號
        df['signal'] = 0
        df.loc[df['total_score'] >= buy_threshold, 'signal'] = 1
        df.loc[df['total_score'] <= sell_threshold, 'signal'] = -1
        df['position_signal'] = df['signal'].ffill().fillna(0)
        
        # 3. 資金管理：分幾塊投入 (Position Sizing)
        # 例如分 4 塊，每塊就是 0.25 的權重
        weight_per_part = 1.0 / parts
        df['current_parts'] = bounded_cumsum(df['position_signal'].values, 0, parts)
        # df['current_parts'] = df['position_signal'].cumsum().clip(0, parts)
        df['strategy_weight'] = df['current_parts'] * weight_per_part
        
        # 4. 績效與結餘計算
        df['market_return'] = df['Close'].pct_change().fillna(0)
        
        # 買入持有 (Buy & Hold) 結餘
        df['buy_and_hold_cumulative_return'] = (1 + df['market_return']).cumprod()
        df['buy_and_hold_balance'] = initial_capital * df['buy_and_hold_cumulative_return']
        
        # 策略結餘 (隔日生效避免 Look-ahead bias)
        df['strategy_daily_return'] = (df['strategy_weight'].shift(1) * df['market_return']).fillna(0)
        df['strategy_cumulative_return'] = (1 + df['strategy_daily_return']).cumprod()
        df['strategy_balance'] = initial_capital * df['strategy_cumulative_return']
        # df.to_csv("backtest_result.csv")
        
        return df, score_matrix

    @staticmethod
    def calculate_metrics(df):
        """計算關鍵績效指標"""
        final_strategy_return = (df['strategy_cumulative_return'].iloc[-1] - 1) * 100
        final_market_return = (df['buy_and_hold_cumulative_return'].iloc[-1] - 1) * 100
        markey_return_diff = final_strategy_return - final_market_return
        markey_return_diff_dir = "up" if markey_return_diff > 0 else "down"
        
        # 最大回撤 (MDD)
        rolling_max = df['strategy_cumulative_return'].cummax()
        drawdown = (df['strategy_cumulative_return'] - rolling_max) / rolling_max
        mdd = drawdown.min() * 100
        
        # 勝率 (以交易次數計)
        # 這裡簡單定義：每日報酬 > 0 為贏
        win_rate = (df[df['strategy_daily_return'] > 0].shape[0] / df[df['strategy_daily_return'] != 0].shape[0]) * 100 if df[df['strategy_daily_return'] != 0].shape[0] > 0 else 0
        
        
        # 僅持有 最大回撤 (MDD)
        bh_rolling_max = df['buy_and_hold_cumulative_return'].cummax()
        bh_drawdown = (df['buy_and_hold_cumulative_return'] - bh_rolling_max) / bh_rolling_max
        bh_mdd = bh_drawdown.min() * 100
        mdd_diff = mdd - bh_mdd
        mdd_diff_dir = "up" if mdd_diff > 0 else "down"
        
        return {
            "Total Return (%)": f"{final_strategy_return:.2f}%",
            "Market Return Diff (%)": f"{markey_return_diff:.2f}",
            "Max Drawdown (%)": f"{mdd:.2f}%",
            "MDD Diff (%)": f"{mdd_diff:.2f}",
            "Win Rate (%)": f"{win_rate:.1f}%",
            "markey_return_diff_dir": markey_return_diff_dir,
            "mdd_diff_dir": mdd_diff_dir,
        }