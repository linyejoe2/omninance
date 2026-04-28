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
from datetime import datetime

from src.core.date_time_util import get_date_tw
from src.db import (
    create_strategy,
    get_current_available_balance,
    get_current_holdings,
    get_trade_records_by_ids,
    update_trade_record,
    list_daily_logs,
    list_trade_records,
    get_activated_strategies,
    stop_strategy,
    StrategyBase
)
from src.service.trader import place_buy_order


router = APIRouter(tags=["strategy"])
logger = logging.getLogger(__name__)

_CHIP_TRACKER_URL = os.environ.get("CHIP_TRACKER_URL", "http://chip-tracker:8000")


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


class CreateStrategyRequest(BaseModel):
    initial_capital: float = 100000.0
    partition: int = 10
    volume_multiplier: float = 2.0
    concentration_slope: float = 0.1
    atr_multiplier: float = 4.0


@router.post("/api/strategies", status_code=201)
async def create_strategy_endpoint(req: CreateStrategyRequest):
    """Create a strategy record and immediately execute its signals."""
    # 將 Request 的內容轉為 StrategyBase
    # 假設 CreateStrategyRequest 的欄位名稱與 StrategyBase 相同
    strategy_data = StrategyBase(**req.model_dump()) 
    
    # 傳遞單一物件進入功能函式
    strategy = await create_strategy(strategy_data)
    return {"strategy": strategy}


@router.get("/api/strategies")
async def list_strategies_endpoint(status: str | None = None):
    return await get_activated_strategies()


@router.post("/api/strategies/{strategy_id}/stop")
async def stop_strategy_endpoint(strategy_id: str):
    ok = await stop_strategy(strategy_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Strategy not found or already stopped")
    return {"status": "stopped", "strategy_id": strategy_id}


@router.get("/api/strategies/{strategy_id}/daily-logs")
async def get_daily_logs(strategy_id: str):
    return await list_daily_logs(strategy_id)


@router.get("/api/trade-records")
async def get_trade_records(strategy_id: str | None = None, limit: int = 100):
    return await list_trade_records(strategy_id, limit)