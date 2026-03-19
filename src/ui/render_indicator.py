import streamlit as st
import inspect

def render_indicator_settings(indicator_list):
    st.header("指標參數設定")
    
    skip_list = ["weight", "color", "min_val", "max_val", "symbol", "current_value", "score", "name"]
    
    COL_COUNT = 3
    
    # 建立一個巢狀結構來儲存所有參數的狀態
    if "indicator_params" not in st.session_state:
        st.session_state.indicator_params = {}

    # 將指標清單按 5 個一組進行分段
    for i in range(0, len(indicator_list), COL_COUNT):
        cols = st.columns(COL_COUNT)
        chunk = indicator_list[i : i + COL_COUNT]
        
        for j, indicator in enumerate(chunk):
            # 計算在原始 list 中的索引
            original_idx = i + j
            
            # 精簡名稱：把 "Indicator" 去掉，畫面才不會塞滿字
            full_name = indicator.__class__.__name__
            display_name = full_name.replace("Indicator", "")
            unique_id = f"{full_name}_{original_idx}"
            
            with cols[j]:
                with st.expander(f"⚙️ {display_name} 設定"):
                    # 1. 自動處理 Weight (每個指標都有)
                    if unique_id not in st.session_state.indicator_params:
                        st.session_state.indicator_params[unique_id] = {"weight": 1.0}
                    
                    # 動態產生 Weight 滑桿
                    st.session_state.indicator_params[unique_id]["weight"] = st.slider(
                        f"權重 (Weight)", 0.0, 1.0, 
                        value=st.session_state.indicator_params[unique_id]["weight"],
                        key=f"weight_{unique_id}"
                    )
                    setattr(indicator, "weight", st.session_state.indicator_params[unique_id]["weight"])

                    # 2. 自動偵測 Indicator 內部的自定義參數 (例如 period, symbol)
                    # 我們排除掉以 _ 開頭的私有屬性與 callable 方法
                    params = {k: v for k, v in indicator.__dict__.items() if not k.startswith('_')}
                    
                    for p_name, p_value in params.items():
                        # 根據型別自動產生 UI
                        if p_name in skip_list: continue # 跳過 weight
                        if isinstance(p_value, int):
                            new_val = st.number_input(f"{p_name}", value=p_value, key=f"{p_name}_{unique_id}")
                        elif isinstance(p_value, float):
                            new_val = st.slider(f"{p_name}", 0.0, 100.0, value=p_value, key=f"{p_name}_{unique_id}")
                        elif isinstance(p_value, str):
                            new_val = st.text_input(f"{p_name}", value=p_value, key=f"{p_name}_{unique_id}")
                        else:
                            continue
                        
                        # 同步回 session_state 與 indicator 物件本身
                        st.session_state.indicator_params[unique_id][p_name] = new_val
                        setattr(indicator, p_name, new_val) # 即時更新物件屬性
