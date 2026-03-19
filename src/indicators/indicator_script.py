import pandas as pd
import streamlit as st
from indicators import BiasIndicator, RSIIndicator, MACDIndicator, BBIndicator, VolumeIndicator, BaseIndicator, BusinessCycleIndicator, LargeHolderIndicator

from indicators import BaseIndicator

@st.cache_resource
def get_indicators(symbol):
    # ✅ 只有當 symbol 改變時才會重新建立物件
    return [
        BiasIndicator(period=10),
        RSIIndicator(),
        MACDIndicator(),
        BBIndicator(),
        VolumeIndicator(),
        BusinessCycleIndicator(),
        LargeHolderIndicator(symbol=symbol)
    ]

def get_total_scores(df: pd.DataFrame, inidcators: list[BaseIndicator]) -> float:
    total_score = 0
    for ind in inidcators:
        print(f"計算指標: {ind.name}, 權重: {ind.weight}")
        ind.calculate(df)
        weighted_score = ind.score * ind.weight
        total_score += weighted_score
    return round(total_score / len(inidcators), 2)