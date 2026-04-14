"""
strategy.py — Strategy CRUD and execution orchestration.

  POST /api/strategies                      — create strategy + execute signals immediately
  GET  /api/strategies                      — list strategies (optional ?status=active|stopped)
  POST /api/strategies/{id}/stop            — stop a strategy
  GET  /api/strategies/{id}/daily-logs      — daily execution log
  GET  /api/trade-records                   — list trade records (optional ?strategy_id=&limit=)
"""
import logging
import os
from datetime import date

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.db import (
    create_strategy,
    insert_daily_log,
    insert_trade_record,
    list_daily_logs,
    list_strategies,
    list_trade_records,
    stop_strategy,
)

router = APIRouter(tags=["strategy"])
logger = logging.getLogger(__name__)

_OMNITRADER_URL = os.environ.get("OMNITRADER_URL", "http://omnitrader:8000")
_CHIP_TRACKER_URL = os.environ.get("CHIP_TRACKER_URL", "http://chip-tracker:8000")


def _to_stock_no(symbol: str) -> str:
    return symbol.split(".")[0]


def execute_signals(strategy_id: str, settings: dict) -> dict:
    """Compute signals via chip-tracker then place buy orders via omnitrader."""
    initial_capital = settings["initial_capital"]
    run_date = date.today().isoformat()

    with httpx.Client(base_url=_CHIP_TRACKER_URL, timeout=60.0) as ct:
        try:
            resp = ct.post("/api/signals/compute", json=settings)
            resp.raise_for_status()
            signal_data = resp.json()
        except Exception as exc:
            logger.error("[Strategy %s] Failed to compute signals: %s", strategy_id, exc)
            insert_daily_log(strategy_id, run_date, None, None, str(exc))
            return {"error": str(exc)}

    buy_list = signal_data.get("actions", {}).get("buy", [])
    sell_hint = signal_data.get("actions", {}).get("sell_hint", [])
    snapshot = signal_data.get("snapshot", {})

    if not buy_list:
        insert_daily_log(strategy_id, run_date, 0, len(sell_hint), None)
        return {"buy": [], "sell_hint": sell_hint, "message": "No buy signals"}

    avg_price = sum(snapshot.get(s, {}).get("p", 0) for s in buy_list) / len(buy_list)
    lots = max(1, int(initial_capital / len(buy_list) / (avg_price * 1000))) if avg_price > 0 else 1

    buy_results: list = []
    errors: list = []

    with httpx.Client(base_url=_OMNITRADER_URL, timeout=10.0) as ot:
        for symbol in buy_list:
            stock_no = _to_stock_no(symbol)
            price = snapshot.get(symbol, {}).get("p")
            try:
                res = ot.post("/api/orders", json={
                    "stock_no": stock_no,
                    "buy_sell": "B",
                    "quantity": lots,
                    "price_flag": "4",
                    "price": None,
                    "user_def": f"omninance-{strategy_id[:8]}",
                })
                insert_trade_record(strategy_id, "buy", symbol, lots, price, res.text, None)
                buy_results.append({"symbol": symbol, "result": res.json()})
                logger.info("[Strategy %s] BUY %s qty=%d", strategy_id, symbol, lots)
            except Exception as exc:
                insert_trade_record(strategy_id, "buy", symbol, lots, price, None, str(exc))
                errors.append({"symbol": symbol, "error": str(exc)})
                logger.error("[Strategy %s] BUY %s failed: %s", strategy_id, symbol, exc)

    error_str = str(errors) if errors else None
    insert_daily_log(strategy_id, run_date, len(buy_list), len(sell_hint), error_str)
    return {"buy": buy_results, "sell_hint": sell_hint, "errors": errors}


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
