import json
import logging
from datetime import date
from pathlib import Path

import pandas as pd
from pandas.tseries.offsets import BDay

ROOT = Path(__file__).parent.parent.parent
logger = logging.getLogger(__name__)

def generate_signals(settings: dict) -> dict:
    """
    實戰訊號產生器：
    1. buy_list:  僅輸出「今天剛翻轉為 True」的新訊號，避免重複買入。
    2. sell_list: 輸出「籌碼訊號消失」的標的（僅供參考）。
    3. snapshot:  提供各標的最新 Close 與 ATR，讓 Node.js 下單機計算移動停損。
    """
    matrix_dir = ROOT / "data" / "matrix"
    dist_dir = ROOT / "dist"
    dist_dir.mkdir(exist_ok=True)

    # 載入矩陣
    price = pd.read_parquet(matrix_dir / "price_matrix.parquet")
    volume = pd.read_parquet(matrix_dir / "volume_matrix.parquet")
    chip_slope = pd.read_parquet(matrix_dir / "chip_matrix.parquet")
    atr_matrix = pd.read_parquet(matrix_dir / "atr_matrix.parquet")

    volume_multiplier = settings["volume_multiplier"]
    concentration_slope = settings["concentration_slope"]
    back_test_period = settings["back_test_period"]

    # 對齊所有矩陣的 columns 與時間軸
    cutoff = pd.Timestamp.today() - pd.DateOffset(years=back_test_period)
    common = (
        price.columns
        .intersection(volume.columns)
        .intersection(chip_slope.columns)
        .intersection(atr_matrix.columns)
    )
    price = price[common][price.index >= cutoff]
    volume = volume[common][volume.index >= cutoff]
    chip_slope = chip_slope[common][chip_slope.index >= cutoff]
    atr_matrix = atr_matrix[common][atr_matrix.index >= cutoff]

    # 進場條件計算 (同 Phase III)
    vol_ma20 = volume.rolling(20).mean()
    entries = (volume > vol_ma20 * volume_multiplier) & (chip_slope > concentration_slope)

    if len(entries) < 2:
        logger.warning("[Signal] 數據不足，無法生成比較訊號")
        return {}

    # --- 關鍵修正：訊號邏輯 ---
    today_sig = entries.iloc[-1]
    yesterday_sig = entries.iloc[-2]

    # 1. 新進場訊號：昨天 False 且 今天變 True (黃金交叉)
    buy_list = today_sig[today_sig & ~yesterday_sig].index.tolist()

    # 2. 籌碼轉弱訊號：昨天 True 且 今天變 False (死魚交叉)
    # 注意：實戰中通常以 ATR 移動停損為準，此 sell_list 作為「提早減碼」參考
    sell_list = yesterday_sig[yesterday_sig & ~today_sig].index.tolist()

    # --- 新增：輸出市場快照 (供下單機計算股數與停損) ---
    latest_prices = price.iloc[-1]
    latest_atrs = atr_matrix.iloc[-1]
    
    # 建立一個包含所有標的最新數據的 Dictionary
    market_snapshot = {}
    for sym in common:
        market_snapshot[sym] = {
            "p": round(float(latest_prices[sym]), 2),
            "atr": round(float(latest_atrs[sym]), 2)
        }

    action_date = (pd.Timestamp.today() + BDay(1)).date().isoformat()
    run_date = date.today().strftime("%Y%m%d")

    signal_data = {
        "metadata": {
            "strategy": "Omninance_Alpha",
            "run_date": run_date,
            "action_date": action_date,
            "params": {
                "partition": settings.get("partition", 10),
                "atr_mult": settings.get("atr_multiplier", 3.0)
            }
        },
        "actions": {
            "buy": buy_list,
            "sell_hint": sell_list,
        },
        "snapshot": market_snapshot
    }

    # 儲存兩個版本：一個帶日期標籤備份，一個固定檔名給下單機
    output_path = dist_dir / f"signals_{run_date}.json"
    latest_path = dist_dir / "latest_signals.json"
    
    json_str = json.dumps(signal_data, indent=2, ensure_ascii=False)
    output_path.write_text(json_str)
    latest_path.write_text(json_str)

    logger.info("[Signal] 成功存檔！(新買點: %d, 轉弱提示: %d)", len(buy_list), len(sell_list))

    return signal_data