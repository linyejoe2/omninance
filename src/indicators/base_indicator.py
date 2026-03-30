from abc import ABC, abstractmethod
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from stock_data import fetch_stock_data
from util import get_line_color

class BaseIndicator(ABC):
    def __init__(self, name, symbol="2330.TW", weight=1.0, min_val=0.0, max_val=100.0, color="#5470c6"):
        self.name = name
        self.weight = weight
        self.min_val = min_val
        self.max_val = max_val
        self.color = color
        
        # Series Data
        self.symbol = symbol
        self.stock_data: pd.DataFrame = fetch_stock_data(symbol)
        self.ind_data = pd.DataFrame()
        self.scores = pd.Series()
        
        # 存儲最後一筆的狀態 (用於儀表板)
        self.current_value = 0.0
        self.score = 0

    @abstractmethod
    def compute_series(self):
        """計算指標的原始數值序列 (如 RSI 曲線)"""
        pass

    @abstractmethod
    def compute_score(self):
        """根據指標數值，轉換為多空評分序列 (-100, 0, 100)"""
        pass

    def calculate(self):
        """整合計算，並更新當前狀態"""
        # 1. 計算數值與分數序列
        self.compute_series()
        self.compute_score()
        
        # 2. 更新當前實例屬性 (給 Streamlit 儀表板使用)
        self.current_value = float(self.ind_data.iloc[-1, -1])
        self.score = int(self.scores.iloc[-1])
        
        # 3. 回傳完整序列 (給回測引擎使用)
        return self.ind_data.iloc[-1], self.scores
    
    
    def render_plot(self):
        """
        在 Streamlit 中渲染該指標的圖表
        """
        self.calculate()
        st.write(f"### {self.name}")
        
        # 建立子圖：兩行一列，高度比例為 3:1，共享 X 軸
        fig = make_subplots(
            rows=2, cols=1, 
            shared_xaxes=True, 
            vertical_spacing=0.05,
            row_heights=[0.7, 0.3]
        )
        
        # 繪製數值
        for col in self.ind_data.columns:
            fig.add_trace(go.Scatter(
                x=self.stock_data.index, 
                y=self.scale_series(self.ind_data[col]), 
                customdata=self.ind_data[col],
                hovertemplate="%{customdata:.2f}",
                mode='lines',
                name= col,
                line=dict(color=get_line_color(self.ind_data.columns.get_loc(col) + 1 - len(self.ind_data.columns)))
            ), row=1, col=1)
        
        # 繪製收盤價
        fig.add_trace(
            go.Scatter(x=self.stock_data.index, y=self.scale_series(self.stock_data['Close']), name='Close', 
                    customdata=self.stock_data['Close'],
                    hovertemplate="%{customdata:.2f}",
                    line=dict(color='rgba(150, 150, 150, 0.8)', width=1)),
            row=1, col=1
        )
        
        # --- Row 2: 分數 ---
        colors = ['red' if c >= o else 'green' for c, o in zip(self.stock_data['Close'], self.stock_data['Open'])]
        
        fig.add_trace(
            go.Bar(x=self.stock_data.index, y=self.scores, name='Scores', 
                marker_color=colors, opacity=0.7),
            row=2, col=1
        )
            
        # 設定圖表樣式
        fig.update_layout(
            height=400, 
            margin=dict(l=10, r=10, t=10, b=10),
            hovermode="x unified",
            showlegend=False,
            yaxis=dict(range=[self.min_val, self.max_val])
        )
        fig.update_yaxes(title_text="Value", range=[self.min_val, self.max_val], row=1, col=1)
        fig.update_yaxes(title_text="Scores", row=2, col=1)
        
        st.plotly_chart(fig, use_container_width=True)
        
        # # 建立一個簡單的兩欄佈局：左邊是數據指標，右邊是圖表
        # col_stat, col_chart = st.columns([1, 4])
        
        # with col_stat:
        #     st.metric(label="當前數值", value=f"{self.current_value:.2f}")
        #     st.metric(label="多空評分", value=self.score, delta=f"{self.score}%")
        #     st.write(f"權重: {self.weight}")

        # with col_chart:
        #     # 使用 Plotly 畫圖，這樣可以自定義顏色和範圍
        #     fig = go.Figure()
        #     fig.add_trace(go.Scatter(
        #         x=df.index, 
        #         y=val_series, 
        #         mode='lines',
        #         name=self.name,
        #         line=dict(color=self.color)
        #     ))
            
        #     # 設定圖表樣式
        #     fig.update_layout(
        #         height=250, 
        #         margin=dict(l=0, r=0, t=0, b=0),
        #         yaxis=dict(range=[self.min_val, self.max_val])
        #     )
        #     st.plotly_chart(fig, use_container_width=True)
        
    def scale_series(self, series: pd.Series):
        if series.name in ["lower_band", "upper_band"]: 
            s_min = self.stock_data["Close"].min()
            s_max = self.stock_data["Close"].max()
        elif series.name == "scores":
            return series
        else:
            s_min = series.min()
            s_max = series.max()
        # 防止除以零（如果價格都沒變）
        if s_max == s_min:
            return series.apply(lambda x: (self.max_val + self.min_val) / 2)
        
        # 執行縮放
        scaled = (series - s_min) / (s_max - s_min) * (self.max_val - self.min_val) + self.min_val
        return scaled