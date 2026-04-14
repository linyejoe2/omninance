import json
import logging
from datetime import date
from pathlib import Path

import pandas as pd
from pandas.tseries.offsets import BDay

ROOT = Path(__file__).parent.parent.parent
logger = logging.getLogger(__name__)


def compute_signals(settings: dict) -> dict:
    """
    實戰訊號計算（不寫入磁碟）：
    1. buy_list:  僅輸出「今天剛翻轉為 True」的新訊號，避免重複買入。
    2. sell_list: 輸出「籌碼訊號消失」的標的（僅供參考）。
    3. snapshot:  提供各標的最新 Close 與 ATR。
    """
    matrix_dir = ROOT / "data" / "matrix"

    price = pd.read_parquet(matrix_dir / "price_matrix.parquet")
    volume = pd.read_parquet(matrix_dir / "volume_matrix.parquet")
    chip_slope = pd.read_parquet(matrix_dir / "chip_matrix.parquet")
    atr_matrix = pd.read_parquet(matrix_dir / "atr_matrix.parquet")

    volume_multiplier = settings["volume_multiplier"]
    concentration_slope = settings["concentration_slope"]
    back_test_period = settings["back_test_period"]

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

    vol_ma20 = volume.rolling(20).mean()
    entries = (volume > vol_ma20 * volume_multiplier) & (chip_slope > concentration_slope)

    if len(entries) < 2:
        logger.warning("[Signal] 數據不足，無法生成比較訊號")
        return {}

    today_sig = entries.iloc[-1]
    yesterday_sig = entries.iloc[-2]

    buy_list = today_sig[today_sig & ~yesterday_sig].index.tolist()
    sell_list = yesterday_sig[yesterday_sig & ~today_sig].index.tolist()

    latest_prices = price.iloc[-1]
    latest_atrs = atr_matrix.iloc[-1]

    market_snapshot = {}
    for sym in common:
        market_snapshot[sym] = {
            "p": round(float(latest_prices[sym]), 2),
            "atr": round(float(latest_atrs[sym]), 2),
        }

    action_date = (pd.Timestamp.today() + BDay(1)).date().isoformat()
    run_date = date.today().strftime("%Y%m%d")

    return {
        "metadata": {
            "strategy": "Omninance_Alpha",
            "run_date": run_date,
            "action_date": action_date,
            "params": {
                "partition": settings.get("partition", 10),
                "atr_mult": settings.get("atr_multiplier", 3.0),
            },
        },
        "actions": {
            "buy": buy_list,
            "sell_hint": sell_list,
        },
        "snapshot": market_snapshot,
    }


def generate_signals(settings: dict) -> dict:
    """Compute signals and persist to dist/."""
    dist_dir = ROOT / "dist"
    dist_dir.mkdir(exist_ok=True)

    signal_data = compute_signals(settings)

    if signal_data:
        run_date = signal_data["metadata"]["run_date"]
        json_str = json.dumps(signal_data, indent=2, ensure_ascii=False)
        (dist_dir / f"signals_{run_date}.json").write_text(json_str)
        (dist_dir / "latest_signals.json").write_text(json_str)
        logger.info(
            "[Signal] 成功存檔！(新買點: %d, 轉弱提示: %d)",
            len(signal_data["actions"]["buy"]),
            len(signal_data["actions"]["sell_hint"]),
        )

    return signal_data
