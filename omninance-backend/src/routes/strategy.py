"""
strategy.py — Strategy CRUD and execution orchestration.

  POST /api/strategies                      — create strategy + execute signals immediately
  GET  /api/strategies                      — list strategies (optional ?status=active|stopped)
  POST /api/strategies/{id}/stop            — stop a strategy
  GET  /api/strategies/{id}/daily-logs      — daily execution log
  GET  /api/trade-records                   — list trade records (optional ?strategy_id=&limit=)
"""
import logging
import asyncio
import os
from datetime import date

import httpx
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Dict, Any, List, Tuple
from src.core.date_time_util import get_date_tw

from src.db import (
    create_strategy,
    insert_daily_log,
    insert_trade_record,
    list_daily_logs,
    list_strategies,
    list_trade_records,
    stop_strategy,
    get_current_available_balance,
    get_current_holdings
)

router = APIRouter(tags=["strategy"])
logger = logging.getLogger(__name__)

_OMNITRADER_URL = os.environ.get("OMNITRADER_URL", "http://omnitrader:8000")
_CHIP_TRACKER_URL = os.environ.get("CHIP_TRACKER_URL", "http://chip-tracker:8000")


def _to_stock_no(symbol: str) -> str:
    return symbol.split(".")[0]

def get_signals(settings: dict)-> Tuple[List[str], List[str], Dict[str, Any], str]:
    """
    呼叫 Chip Tracker API 計算策略訊號。
    回傳: (buy_list, sell_hint, snapshot, error_message)
    """
    with httpx.Client(base_url=_CHIP_TRACKER_URL, timeout=60.0) as ct:
        try:
            resp = ct.post("/api/signals/compute", json=settings)
            resp.raise_for_status()
            signal_data = resp.json()
        except Exception as exc:
            return [], [], {}, str(exc)

    buy_list = signal_data.get("actions", {}).get("buy", [])
    sell_hint = signal_data.get("actions", {}).get("sell_hint", [])
    snapshot = signal_data.get("snapshot", {})
    return buy_list, sell_hint, snapshot

async def execute_signals(strategy_id: str, settings: dict, background_tasks: BackgroundTasks) -> dict:
    """Compute signals via chip-tracker then place buy orders via omnitrader."""
    partition = settings["partition"]
    run_date = get_date_tw().isoformat()
    available_balance = get_current_available_balance(strategy_id)
    today_holdings = [h['symbol'] for h in get_current_holdings(strategy_id)]
    
    
    buy_list, _, snapshot, error = get_signals(settings)
    if error:
        insert_daily_log(strategy_id, run_date, error=error)
        return {"message": error}
    
    # 3. 資金分配計算 (計算每標的分多少錢)
    buy_plans = {}
    temp_cash = available_balance
    for symbol in buy_list:
        # 已經持有的就不再買
        if symbol in today_holdings:
            continue
        
        fund = temp_cash * (1 / partition)
        if fund < 1000: # 低消過濾
            continue
            
        buy_plans[symbol] = fund
        temp_cash -= fund # 動態扣除，確保不超買
        
    # 4. 執行下單並記錄 PENDING 狀態
    async def place_single_order(client: httpx.AsyncClient, symbol: str, fund: float):
        try:
            payload = {"stock_no": symbol, "tick": 2, "fund": fund, "user_def": f"omni-{strategy_id[:8]}"}
            res = await client.post("/api/orders/aggressive-limit-order", json=payload)
            data = res.json()
            
            # 建立初始 PENDING 紀錄
            record_id = insert_trade_record(
                strategy_id=strategy_id, action="BUY", symbol=symbol,
                status="PENDING", order_id=data.get("ord_no"), result=res.text
            )
            return record_id
        except Exception as e:
            logger.error(f"Async order failed for {symbol}: {e}")
            return None
        
    # 並行執行所有下單請求
    async with httpx.AsyncClient(base_url=_OMNITRADER_URL, timeout=20.0) as client:
        tasks = [place_single_order(client, s, f) for s, f in buy_plans.items()]
        record_ids = await asyncio.gather(*tasks)
        
    # 過濾出成功的 record_ids，交給背景任務去追蹤
    successful_ids = [rid for rid in record_ids if rid is not None]
    
    if successful_ids:
        # 註冊背景任務：傳入剛建立的 record_ids 進行輪詢
        background_tasks.add_task(poll_order_status, strategy_id, successful_ids)

    return {"status": "orders_sent", "count": len(successful_ids)}

async def poll_order_status(strategy_id: str, record_ids: list):
    """
    在背景不斷檢查訂單狀態，直到全部 FILLED/FAILED
    """
    max_attempts = 30  # 最多檢查 30 次
    attempt = 0
    pending_ids = set(record_ids)

    async with httpx.AsyncClient(base_url=_OMNITRADER_URL, timeout=10.0) as client:
        while pending_ids and attempt < max_attempts:
            await asyncio.sleep(5)  # 每 5 秒檢查一次
            attempt += 1
            
            try:
                # 取得今日所有委託回報
                resp = await client.get("/api/orders")
                api_orders = {o["ord_no"]: o for o in resp.json() if o.get("ord_no")}
                
                # 檢查我們關心的那些 record_id
                # 這裡需要一個輔助 function: get_trade_records_by_ids 拿到 order_id
                records = get_trade_records_by_ids(list(pending_ids))
                
                for rec in records:
                    ord_no = rec['order_id']
                    if ord_no in api_orders:
                        order_info = api_orders[ord_no]
                        
                        # 判斷成交狀態 (台股 mat_qty_share == org_qty_share)
                        if order_info["mat_qty_share"] >= order_info["org_qty_share"]:
                            update_trade_record(
                                rec['_id'], status="FILLED", 
                                price=order_info["avg_price"], 
                                filled_qty=order_info["mat_qty_share"]
                            )
                            pending_ids.remove(rec['_id'])
                        elif order_info.get("err_code") != "00000000":
                            update_trade_record(rec['_id'], status="FAILED", error=order_info["err_msg"])
                            pending_ids.remove(rec['_id'])
                            
            except Exception as e:
                logger.error(f"Polling error: {e}")

        # 如果超過次數還沒成交，標記為超時或手動處理
        for remaining_id in pending_ids:
            update_trade_record(remaining_id, status="TIMEOUT", error="Wait for filled timeout")


class CreateStrategyRequest(BaseModel):
    initial_capital: float = 100000.0
    partition: int = 10
    volume_multiplier: float = 2.0
    concentration_slope: float = 0.02
    atr_multiplier: float = 4.0
    back_test_period: int = 4


@router.post("/api/strategies", status_code=201)
def create_strategy_endpoint(req: CreateStrategyRequest):
    """Create a strategy record and immediately execute its signals."""
    strategy = create_strategy(
        req.initial_capital, req.partition, req.volume_multiplier,
        req.concentration_slope, req.atr_multiplier, req.back_test_period,
    )
    execution = execute_signals(strategy["_id"], req.model_dump())
    return {"strategy": strategy, "execution": execution}


@router.get("/api/strategies")
def list_strategies_endpoint(status: str | None = None):
    return list_strategies(status)


@router.post("/api/strategies/{strategy_id}/stop")
def stop_strategy_endpoint(strategy_id: str):
    ok = stop_strategy(strategy_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Strategy not found or already stopped")
    return {"status": "stopped", "strategy_id": strategy_id}


@router.get("/api/strategies/{strategy_id}/daily-logs")
def get_daily_logs(strategy_id: str):
    return list_daily_logs(strategy_id)


@router.get("/api/trade-records")
def get_trade_records(strategy_id: str | None = None, limit: int = 100):
    return list_trade_records(strategy_id, limit)
