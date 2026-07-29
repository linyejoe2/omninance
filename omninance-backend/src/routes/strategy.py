"""
strategy.py — Strategy CRUD and read APIs over the PostgreSQL trading store.

  POST /api/strategies                      — create strategy (+ generate next-day signals in background)
  GET  /api/strategies                      — list strategies (optional ?status=active|stopped)
  POST /api/strategies/{id}/stop            — stop a strategy
  GET  /api/strategies/{id}/positions       — current open positions
  GET  /api/strategies/{id}/daily-logs      — daily logs, newest first
  GET  /api/order-records                   — order records (optional ?strategy_id=&limit=)

  The strategy jobs (daily-strategies, finalize-daily-settlement,
  nightly-signal-generate — see src/service/strategy_schedule.py) have no
  dedicated route here; the ofelia scheduler triggers them the same way the
  dashboard's manual "force execute" does, via
  POST /api/schedules/{job}/trigger (src/routes/schedule.py).
"""
import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from src.core.decimal_util import to_decimal
from src.db import get_session
from src.models.trading import Strategy, StrategyStatus
from src.modules.trading_engine import generate_daily_signals
from src.repositories import daily_log_repo, order_record_repo, position_repo, strategy_repo

router = APIRouter(tags=["strategy"])
logger = logging.getLogger(__name__)


class CreateStrategyRequest(BaseModel):
    name: str = "Omninance Alpha"
    initial_capital: float = 100000.0
    position_slots: int = 10
    volume_multiplier: float = 2.0
    concentration_slope: float = 0.1
    atr_multiplier: float = 4.0


@router.post("/api/strategies", status_code=201)
async def create_strategy_endpoint(req: CreateStrategyRequest, background_tasks: BackgroundTasks):
    """Create a strategy; its first daily log is generated in the background
    (signal computation takes minutes), execution starts next trading morning."""
    strategy = Strategy(
        name=req.name,
        initial_capital=to_decimal(req.initial_capital),
        position_slots=req.position_slots,
        volume_multiplier=req.volume_multiplier,
        concentration_slope=req.concentration_slope,
        atr_multiplier=req.atr_multiplier,
    )
    async with get_session() as session:
        await strategy_repo.create_strategy(session, strategy)
        await session.commit()

    background_tasks.add_task(generate_daily_signals, strategy)
    return {"strategy": strategy}


@router.get("/api/strategies")
async def list_strategies_endpoint(status: Optional[str] = None):
    parsed_status: Optional[StrategyStatus] = None
    if status is not None:
        try:
            parsed_status = StrategyStatus(status)
        except ValueError:
            raise HTTPException(status_code=422, detail=f"Invalid status: {status}")

    async with get_session() as session:
        return await strategy_repo.list_strategies(session, parsed_status)


@router.post("/api/strategies/{strategy_id}/stop")
async def stop_strategy_endpoint(strategy_id: str):
    async with get_session() as session:
        ok = await strategy_repo.stop_strategy(session, strategy_id)
        if not ok:
            raise HTTPException(status_code=404, detail="Strategy not found or already stopped")
        await session.commit()
    return {"status": "stopped", "strategy_id": strategy_id}


@router.get("/api/strategies/{strategy_id}/positions")
async def list_positions_endpoint(strategy_id: str):
    async with get_session() as session:
        if await strategy_repo.get_strategy(session, strategy_id) is None:
            raise HTTPException(status_code=404, detail="Strategy not found")
        return await position_repo.list_positions(session, strategy_id)


@router.get("/api/strategies/{strategy_id}/daily-logs")
async def list_daily_logs_endpoint(strategy_id: str, limit: Optional[int] = None):
    async with get_session() as session:
        if await strategy_repo.get_strategy(session, strategy_id) is None:
            raise HTTPException(status_code=404, detail="Strategy not found")
        return await daily_log_repo.list_logs(session, strategy_id, limit)


@router.get("/api/order-records")
async def list_order_records_endpoint(strategy_id: Optional[str] = None, limit: int = 100):
    async with get_session() as session:
        return await order_record_repo.list_orders(session, strategy_id, limit)
