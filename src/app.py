import streamlit as st
import pandas as pd
from backtest.backtester import BacktestEngine
from stock_data import fetch_stock_data
from streamlit_echarts import st_echarts
from indicators import BiasIndicator, RSIIndicator, MACDIndicator, BBIndicator, VolumeIndicator, BaseIndicator, BusinessCycleIndicator
from streamlit_sortables import sort_items
from ui import render_gauge_chart
from db import db

st.set_page_config(page_title="Omninance AI", layout="wide")
st.title("📈 多指標物件化決策系統")

# --- Sidebar 邏輯 ---
# st.sidebar.header("📁 診斷管理")

# --- 定義觸發邏輯 ---
def handle_search():
    # 從 session_state 抓取輸入的值
    val = st.session_state.symbol_input.upper()
    if val:
        db.add_or_update_history(val)
        st.session_state.current_symbol = val
        # 清空輸入框（選用，若想保留則註解掉下一行）
        # st.session_state.symbol_input = ""
    st.rerun()

# 1. 新增輸入框
with st.sidebar.container():
    new_symbol = st.text_input(
            "查詢股票", 
            value="", 
            placeholder="例如: 2330.TW",
            key="symbol_input", 
            on_change=handle_search  # 按下 Enter 時觸發
        ).upper()
    if st.button("開始分析", use_container_width=True):
        handle_search()

# 2. 歷史紀錄列表
history = db.get_search_history()

if history:
    st.sidebar.write("---")
    st.sidebar.caption("歷史紀錄")
    
    for item in history:
        h_symbol = item['symbol']
        is_pinned = item['is_pinned']
        h_name = item.get('name') or ""
        # 取得名稱前兩個字，如果名稱太短則直接顯示
        display_name = h_name[:2] if h_name else ""
        display_symbol = h_symbol.replace('.TW', '')
        
        # 組合顯示文字，例如 "2330.TW 台積" 或 "AAPL.US"
        btn_label = f"{'📍 ' if is_pinned else ''}{display_symbol} {display_name}".strip()
        
        # 使用 columns 做出 [名稱 | 釘選 | 刪除] 的排版
        col_name, col_pin, col_del = st.sidebar.columns([3, 1, 1])
        
        with col_name:
            if st.session_state.get("current_symbol") is None:
                st.session_state.current_symbol = h_symbol
            
            # 判斷是否為目前選中
            is_active = (h_symbol == st.session_state.current_symbol)
            btn_type = "primary" if is_active else "secondary"
            
            if st.button(btn_label, key=f"sel_{h_symbol}", use_container_width=True, type=btn_type):
                db.add_or_update_history(h_symbol) # 更新訪問時間 (自動置頂)
                st.session_state.current_symbol = h_symbol
                st.rerun()
        
        with col_pin:
            pin_icon = "📌" if is_pinned else "📍"
            if st.button(pin_icon, key=f"pin_{h_symbol}"):
                db.toggle_pin(h_symbol, is_pinned)
                st.rerun()
                
        with col_del:
            if st.button("🗑️", key=f"del_{h_symbol}"):
                db.delete_history(h_symbol)
                # 如果刪除的是當前選中的，切換到第一個
                if h_symbol == st.session_state.current_symbol:
                    st.session_state.current_symbol = "2330.TW" 
                st.rerun()

# 最終執行分析
symbol = st.session_state.current_symbol
data = fetch_stock_data(symbol)

with st.sidebar:
    if st.button("🔄 同步景氣指標"):
        with st.spinner("正在連線國發會..."):
            success, message = db.sync_business_cycle_data()
            if success:
                st.toast(message, icon="✅")
            else:
                st.error(message)

if not data.empty:
    indicator_list: list[BaseIndicator] = [
        BiasIndicator(period=10),
        RSIIndicator(),
        MACDIndicator(),
        BBIndicator(),
        VolumeIndicator(),
        BusinessCycleIndicator()
    ]

    total_score = 0
    for ind in indicator_list:
        ind.calculate(data)
        total_score += ind.score

    tab_current, tab_backtest = st.tabs(["💡 當前指標矩陣", "📉 歷史數據預覽"])

    with tab_current:
        st.subheader("🔍 分項指標狀態")
        n_cols = len(indicator_list)
        cols = st.columns(n_cols)
        
        for j in range(n_cols):
            indicator = indicator_list[j]
            with cols[j]:
                # 1. 渲染儀表板
                st_echarts(
                    render_gauge_chart(indicator), 
                    height="180px", 
                    key=f"gauge_{j}"
                )
                
                # 2. 顯示分項分數與數值
                # 利用 delta 來顯示分數的正負顏色 (正為綠/向上，負為紅/向下)
                st.header(f"{indicator.name}")
                st.header(f"{indicator.current_value:.2f}")
                st.caption(f"Score: {indicator.score}")

        st.divider()

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
        # --- 策略設定區 ---
        with st.expander("⚙️ 策略參數設定", expanded=True):
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                init_cap = st.number_input("初始資金 (TWD)", value=100000, step=10000)
            with c2:
                parts = st.number_input("資金分幾等份投入", min_value=1, max_value=10, value=1)
            with c3:
                buy_th = st.slider("買入總分門檻", -5, 5, 2)
            with c4:
                sell_th = st.slider("賣出總分門檻", -5, 5, -1)
                
                
        st.subheader(f"📊 {symbol} 策略回測報告")
        
        # 執行回測
        result_df, score_matrix = BacktestEngine.run(
            data, indicator_list, 
            initial_capital=init_cap, 
            parts=parts, 
            buy_threshold=buy_th, 
            sell_threshold=sell_th
        )
        metrics = BacktestEngine.calculate_metrics(result_df)
        
        # 1. 顯示績效指標 (Metrics)
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("策略總報酬", metrics["Total Return (%)"], delta=f"對比持有 {metrics['Market Return Diff (%)']}%"
            , delta_arrow=metrics["markey_return_diff_dir"]
            , delta_color="green" if metrics["markey_return_diff_dir"] == "up" else "red"
            )
        m2.metric("最大回撤 (MDD)", metrics["Max Drawdown (%)"], delta=f"對比持有 {metrics['MDD Diff (%)']}%"
            , delta_arrow=metrics["mdd_diff_dir"]
            , delta_color="green" if metrics["mdd_diff_dir"] == "up" else "red"
            )
        m3.metric("交易勝率", metrics["Win Rate (%)"])
        m4.metric("目前持倉狀態", "做多" if result_df['position_signal'].iloc[-1] > 0 else "空手")
        
        st.write("---")
        
        # 2. 顯示報酬曲線圖
        st.write("📈 累積報酬曲線 (策略 vs 持有)")
        # 這裡我們把日期轉成字串方便展示
        plot_df = result_df[['buy_and_hold_balance', 'strategy_balance']].copy().rename(columns={
            'buy_and_hold_balance': '買入後持有淨值',
            'strategy_balance': '策略淨值'
        })
        st.line_chart(plot_df)

        # 3. 顯示指標共振熱圖 (或是分數明細)
        # --- 詳細表格 ---
        st.write("📄 每日績效與結餘明細")
        display_df = result_df[[
            'Close', 'total_score', 'strategy_weight', 
            'buy_and_hold_balance', 'strategy_balance'
        ]].copy()
        
        # 格式化顯示
        display_df['buy_and_hold_balance'] = display_df['buy_and_hold_balance'].map("${:,.0f}".format)
        display_df['strategy_balance'] = display_df['strategy_balance'].map("${:,.0f}".format)
        
        st.dataframe(display_df.sort_index(ascending=False),
            column_config={
                "Close": "收盤價",
                "total_score": "綜合分數",
                "strategy_weight": "部位比例",
                "buy_and_hold_balance": "買入後持有淨值",
                "strategy_balance": "策略淨值"
            }, 
            width='stretch'
        )

else:
    st.error("無法獲取數據，請檢查輸入的代碼是否正確。")
