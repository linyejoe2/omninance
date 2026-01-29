import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
from abc import ABC, abstractmethod
from streamlit_echarts import st_echarts
from pyecharts.commons.utils import JsCode

# ==========================================
# 1. 指標物件化框架 (The Framework)
# ==========================================

class BaseIndicator(ABC):
    """指標基類，所有新指標都必須繼承此類"""
    def __init__(self, name):
        self.name = name
        self.value = 0.0      # 當前指標數值
        self.score = 0        # 評分: -1(空), 0(中), 1(多)
        self.min_val = 0.0    # 儀表板最小值
        self.max_val = 100.0  # 儀表板最大值
        self.color = "#5470c6"

    @abstractmethod
    def calculate(self, df):
        """輸入 DataFrame 並計算指標數值與評分"""
        pass

# --- 具體指標實作 ---

class BiasIndicator(BaseIndicator):
    def __init__(self):
        super().__init__("乖離率 (BIAS)")
        self.min_val = -10.0
        self.max_val = 10.0
        self.color = "#91cc75"

    def calculate(self, df):
        sma20 = ta.sma(df['Close'], length=20)
        bias = ((df['Close'] - sma20) / sma20) * 100
        self.value = float(bias.iloc[-1])
        # 邏輯：負乖離過大看多(+1)，正乖離過大看空(-1)
        self.score = 1 if self.value < -3 else (-1 if self.value > 3 else 0)

class RSIIndicator(BaseIndicator):
    def __init__(self):
        super().__init__("RSI 強弱指標")
        self.min_val = 0.0
        self.max_val = 100.0
        self.color = "#fac858"

    def calculate(self, df):
        rsi = ta.rsi(df['Close'], length=14)
        self.value = float(rsi.iloc[-1])
        # 邏輯：低於30超賣(+1)，高於70超買(-1)
        self.score = 1 if self.value < 30 else (-1 if self.value > 70 else 0)

class MACDIndicator(BaseIndicator):
    def __init__(self):
        super().__init__("MACD 動能")
        self.min_val = -2.0
        self.max_val = 2.0
        self.color = "#73c0de"

    def calculate(self, df):
        macd_df = ta.macd(df['Close'])
        # 取得 MACD Histograms (柱狀體)
        hist_col = [c for c in macd_df.columns if 'MACDh' in c][0]
        self.value = float(macd_df[hist_col].iloc[-1])
        self.min_val = float(macd_df[hist_col].min())
        self.max_val = float(macd_df[hist_col].max())
        # 邏輯：紅柱(+1)，綠柱(-1)
        self.score = 1 if self.value > 0 else -1

class BBIndicator(BaseIndicator):
    def __init__(self):
        super().__init__("布林通道位置")
        self.min_val = 0.0 # 0 代表下軌，100 代表上軌
        self.max_val = 100.0

    def calculate(self, df):
        bb = ta.bbands(df['Close'], length=20)
        lower = bb.iloc[-1, 0] # BBL
        upper = bb.iloc[-1, 2] # BBU
        current = df['Close'].iloc[-1]
        
        # 計算價格在通道中的百分比位置
        position = ((current - lower) / (upper - lower)) * 100
        self.value = float(position)
        # 邏輯：靠近下軌(<20)看多，靠近上軌(>80)看空
        self.score = 1 if self.value < 20 else (-1 if self.value > 80 else 0)

class VolumeIndicator(BaseIndicator):
    def __init__(self):
        super().__init__("成交量能")
        self.min_val = 0.0
        self.max_val = 2.0 # 相對於均量的倍數

    def calculate(self, df):
        avg_vol = df['Volume'].rolling(20).mean().iloc[-1]
        curr_vol = df['Volume'].iloc[-1]
        self.value = float(curr_vol / avg_vol)
        # 邏輯：量增超過均量 20% 給予加分
        self.score = 1 if self.value > 1.2 else 0

# ==========================================
# 2. 工具函數 (Tools)
# ==========================================

def render_gauge_chart(ind):
    """產出帶有『建議狀態顏色』的儀表板配置"""
    
    # 根據 score 定義顏色與樣式
    # 台灣股市習慣：漲(多)為紅，跌(空)為綠。但依照你的需求：綠色買進、紅色賣出
    bg_color = "transparent"
    text_color = "#333"
    
    # 1. 先在外部算好數值，確保傳入 JS 的是乾淨的數字
    m_val = float(ind.min_val)
    max_v = float(ind.max_val)

    # 2. 使用更簡潔的寫法，移除多餘的換行與縮排
    # 早期版本對格式非常敏感
    js_formatter = JsCode(
        f"function(value) {{"
        f"  var p = Math.round((value - {m_val}) / ({max_v} - {m_val}) * 100);"
        f"  var targets = [0, 30, 50, 70, 100];"
        f"  if (targets.indexOf(p) !== -1) return value;"
        f"  return '';"
        f"}}"
    )
    
    if ind.score >= 1:    # 買進/多頭建議
        text_color = "#008046" 
        if ind.score >= 2: # 強力建議 (類似漲停反白)
            bg_color = "#00ba67" # 綠色背景
            text_color = "#ffffff"
    elif ind.score <= -1: # 賣出/空頭建議
        text_color = "#b91d1d"
        if ind.score <= -2: # 強力建議 (類似跌停反白)
            bg_color = "#ff4b4b" # 紅色背景
            text_color = "#ffffff"

    return {
        "series": [{
            "type": 'gauge',
            "startAngle": 210,
            "endAngle": -30,
            "min": round(float(ind.min_val), 2),
            "max": round(float(ind.max_val), 2),
            "splitNumber": 4,
            "radius": '100%',
            "axisLine": {
                "distance": -15,
                "lineStyle": {
                    "width": 15,
                    "color": [[0.3, '#67e0e3'], [0.7, '#fac858'], [1, '#fd666d']]
                }
            },
            "splitLine": {
                "distance": -15,
                "length": 15,
                "lineStyle": {
                "color": '#fff',
                "width": 4
                }
            },
            "axisTick": {
                "distance": -15,
                "length": 8,
                "lineStyle": {
                "color": '#fff',
                "width": 2
                }
            },
            "axisLabel": {
                "distance": 10, 
                "color": '#fff', 
                "fontSize": 14,
                "show": True
            },
            "pointer": {"width": 3, "length": '60%'},
            "title": {
                "offsetCenter": [0, '85%'],
                "fontSize": 24,
                "color": "#fff",
                "show": True
            },
            "detail": {
                "offsetCenter": [0, '60%'],
                "valueAnimation": True,
                # 使用 rich 樣式來達成反白效果
                "formatter": "{style|{value}}",
                "rich": {
                    "style": {
                        "fontSize": 18,
                        "fontWeight": 'bold',
                        "color": text_color,
                        "backgroundColor": bg_color,
                        "padding": [2, 6],
                        "borderRadius": 4
                    }
                }
            },
            "data": [{"value": round(float(ind.value), 2), "name": ind.name}]
        }]
    }

# ==========================================
# 3. Streamlit App 主程式
# ==========================================

st.set_page_config(page_title="Omninance AI", layout="wide")
st.title("📈 多指標物件化決策系統")

# Sidebar
symbol = st.sidebar.text_input("輸入股票代碼", value="2330.TW")
analyze_btn = st.sidebar.button("開始診斷")

# 下載數據
@st.cache_data(ttl=3600)
def fetch_stock_data(ticker):
    df = yf.download(ticker, period="1y", auto_adjust=True)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.columns = df.columns.astype(str)
    return df

data = fetch_stock_data(symbol)

if not data.empty:
    # --- 指標物件陣列 ---
    indicator_list = [
        BiasIndicator(),
        RSIIndicator(),
        MACDIndicator(),
        BBIndicator(),
        VolumeIndicator()
    ]

    # 計算所有指標
    total_score = 0
    for ind in indicator_list:
        ind.calculate(data)
        total_score += ind.score

    tab_current, tab_backtest = st.tabs(["💡 當前指標矩陣", "📉 歷史數據預覽"])

    with tab_current:
        # 1. 指標儀表板 Grid (每列 3 個)
        st.subheader("🔍 分項指標狀態")
        n_cols = 5
        for i in range(0, len(indicator_list), n_cols):
            cols = st.columns(n_cols)
            for j in range(n_cols):
                if i + j < len(indicator_list):
                    with cols[j]:
                        st_echarts(render_gauge_chart(indicator_list[i+j]), height="180px", key=f"gauge_{i}_{j}")

        st.divider()

        # 2. 總結儀表板
        st.subheader("🏁 綜合決策建議")
        max_possible_score = len(indicator_list)
        
        summary_option = {
            "series": [{
                "type": 'gauge',
                "min": -max_possible_score, "max": max_possible_score,
                "splitNumber": max_possible_score * 2,
                "axisLine": {"lineStyle": {"width": 15, "color": [[0.3, '#fd666d'], [0.7, '#fac858'], [1, '#67e0e3']]}},
                "detail": {"formatter": '{value}', "fontSize": 30},
                "data": [{"value": total_score, "name": "綜合多空評分"}]
            }]
        }
        
        c1, c2 = st.columns([2, 1])
        with c1:
            st_echarts(summary_option, height="400px")
        with c2:
            st.write("### 判斷結果")
            if total_score >= 2:
                st.success(f"🔥 強力看多 ({total_score}分)")
                st.write("多項指標達成共振，目前市場動能強勁且未過度噴發。")
            elif total_score <= -2:
                st.error(f"⚠️ 警示看空 ({total_score}分)")
                st.write("指標顯示市場過熱或動能轉弱，建議縮減部位。")
            else:
                st.info(f"⚖️ 中性盤整 ({total_score}分)")
                st.write("目前訊號互相抵消，建議靜待突破或區間操作。")

    with tab_backtest:
        st.dataframe(data.tail(10), use_container_width=True)
        st.line_chart(data['Close'])

else:
    st.error("無法獲取數據，請檢查輸入的代碼是否正確。")