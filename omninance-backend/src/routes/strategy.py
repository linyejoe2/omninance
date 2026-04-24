"""
strategy.py — Strategy CRUD and execution orchestration.

  POST /api/strategies                      — create strategy + execute signals immediately
  GET  /api/strategies                      — list strategies (optional ?status=active|stopped)
  POST /api/strategies/{id}/stop            — stop a strategy
  GET  /api/strategies/{id}/daily-logs      — daily execution log
  GET  /api/trade-records                   — list trade records (optional ?strategy_id=&limit=)
"""
import asyncio
import logging
import os
from typing import Any, Dict, List, Tuple

import httpx
from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from src.core.date_time_util import get_date_tw
from src.db import (
    create_strategy,
    get_current_available_balance,
    get_current_holdings,
    get_trade_records_by_ids,
    insert_daily_log,
    insert_trade_record,
    list_daily_logs,
    list_strategies,
    list_trade_records,
    stop_strategy,
    update_trade_record,
)

router = APIRouter(tags=["strategy"])
logger = logging.getLogger(__name__)

_OMNITRADER_URL = os.environ.get("OMNITRADER_URL", "http://omnitrader:8000")
_CHIP_TRACKER_URL = os.environ.get("CHIP_TRACKER_URL", "http://chip-tracker:8000")


def _to_stock_no(symbol: str) -> str:
    return symbol.split(".")[0]


def get_signals(settings: dict) -> Tuple[List[str], List[str], Dict[str, Any], str]:
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
    return buy_list, sell_hint, snapshot, ""


async def poll_order_status(strategy_id: str, record_ids: list[int]) -> None:
    """
    背景任務：輪詢委託狀態，直到全部 FILLED / FAILED / TIMEOUT。
    """
    max_attempts = 30
    attempt = 0
    pending_ids = set(record_ids)
    wait_time = 10

    async with httpx.AsyncClient(base_url=_OMNITRADER_URL, timeout=10.0) as client:
        while pending_ids and attempt < max_attempts:# 1. 執行等待
            logger.info(f"[Polling] Attempt {attempt+1}, waiting {wait_time}s...")
            await asyncio.sleep(wait_time)
            
            wait_time *= 2
            attempt += 1

            try:
                resp = await client.get("/api/orders")
                api_orders: dict = {o["ord_no"]: o for o in resp.json() if o.get("ord_no")}

                records = get_trade_records_by_ids(list(pending_ids))

                for rec in records:
                    ord_no = rec["order_id"]
                    if ord_no not in api_orders:
                        continue

                    order_info = api_orders[ord_no]
                    filled = order_info.get("mat_qty_share", 0)
                    total  = order_info.get("org_qty_share", 0)

                    if filled >= total and total > 0:
                        update_trade_record(
                            rec["_id"],
                            status="FILLED",
                            filled_qty=filled,
                        )
                        pending_ids.discard(rec["_id"])
                    elif order_info.get("err_code", "00000000") != "00000000":
                        update_trade_record(
                            rec["_id"],
                            status="FAILED",
                            error=order_info.get("err_msg"),
                        )
                        pending_ids.discard(rec["_id"])

            except Exception as exc:
                logger.error("[Poll] Error checking orders: %s", exc)

    for remaining_id in pending_ids:
        update_trade_record(remaining_id, status="TIMEOUT", error="Wait for filled timeout")


async def execute_signals(
    strategy_id: str,
    settings: dict,
    background_tasks: BackgroundTasks = None,
) -> dict:
    """Compute signals via chip-tracker then place buy orders via omnitrader."""
    partition = settings["partition"]
    run_date = get_date_tw().isoformat()
    available_balance = get_current_available_balance(strategy_id)
    today_holdings = {h["symbol"] for h in get_current_holdings(strategy_id)}

    buy_list, _, snapshot, error = get_signals(settings)
    if error:
        insert_daily_log(strategy_id, run_date, error=error)
        return {"message": error}

    # 資金分配：每份 = 可用餘額 ÷ partition；已持有的跳過
    buy_plans: Dict[str, float] = {}
    temp_cash = available_balance
    for symbol in buy_list:
        if symbol in today_holdings:
            continue
        fund = temp_cash * (1 / partition)
        if fund < 1000:
            continue
        buy_plans[symbol] = fund
        temp_cash -= fund

    if not buy_plans:
        insert_daily_log(strategy_id, run_date)
        return {"status": "no_orders", "message": "No new buy targets"}

    # 並行下單
    async def place_single_order(
        client: httpx.AsyncClient, symbol: str, fund: float
    ) -> int | None:
        try:
            payload = {
                "stock_no": _to_stock_no(symbol),
                "tick": 2,
                "fund": fund,
                "user_def": f"omni-{strategy_id[:8]}",
            }
            res = await client.post("/api/orders/aggressive-limit-order", json=payload)
            data = res.json()
            record_id = insert_trade_record(
                strategy_id=strategy_id,
                order_id=data.get("ord_no"),
                action="BUY",
                symbol=symbol,
                quantity=None,
                price=None,
                status="PENDING",
                result=res.text,
            )
            return record_id
        except Exception as exc:
            logger.error("[Execute] Order failed for %s: %s", symbol, exc)
            insert_trade_record(
                strategy_id=strategy_id,
                order_id=None,
                action="BUY",
                symbol=symbol,
                quantity=None,
                price=None,
                status="FAILED",
                error=str(exc),
            )
            return None

    async with httpx.AsyncClient(base_url=_OMNITRADER_URL, timeout=20.0) as client:
        tasks = [place_single_order(client, s, f) for s, f in buy_plans.items()]
        record_ids = await asyncio.gather(*tasks)

    successful_ids = [rid for rid in record_ids if rid is not None]

    if successful_ids:
        if background_tasks:
            # API 情境：交給 FastAPI 管理背景任務
            background_tasks.add_task(poll_order_status, strategy_id, successful_ids)
        else:
            # Scheduler 情境：手動丟進原生 asyncio event loop
            # 這樣不會阻塞主排程，且能確保 polling 繼續執行
            asyncio.create_task(poll_order_status(strategy_id, successful_ids))

    insert_daily_log(strategy_id, run_date)
    return {"status": "orders_sent", "count": len(successful_ids)}


class CreateStrategyRequest(BaseModel):
    initial_capital: float = 100000.0
    partition: int = 10
    volume_multiplier: float = 2.0
    concentration_slope: float = 0.02
    atr_multiplier: float = 4.0
    back_test_period: int = 4


@router.post("/api/strategies", status_code=201)
async def create_strategy_endpoint(req: CreateStrategyRequest, background_tasks: BackgroundTasks):
    """Create a strategy record and immediately execute its signals."""
    strategy = create_strategy(
        req.initial_capital, req.partition, req.volume_multiplier,
        req.concentration_slope, req.atr_multiplier, req.back_test_period,
    )
    execution = await execute_signals(strategy["_id"], req.model_dump(), background_tasks)
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
