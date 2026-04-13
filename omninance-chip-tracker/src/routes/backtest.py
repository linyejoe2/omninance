"""
backtest.py — Run Phase III vectorbt backtest on demand and return JSON results.

  POST /api/backtest
    Body: BacktestRequest (all fields optional — defaults match setting.json)
    Returns: { stats, benchmark_stats, chart }
      chart: [{ date, strategy, benchmark, buy_count, sell_count, hold_count }]
             strategy/benchmark normalised to 100 at t0; counts are raw integers
"""
import asyncio
import logging
import math

import numpy as np
import vectorbt as vbt
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.main import compute_portfolio

router = APIRouter(tags=["backtest"])
logger = logging.getLogger(__name__)


class BacktestRequest(BaseModel):
    initial_capital: float = 100000.0
    partition: int = 10
    volume_multiplier: float = 2.0
    concentration_slope: float = 0.02
    atr_multiplier: float = 4.0
    back_test_period: int = 4


def _serialize(v):
    """Convert a vectorbt/pandas/numpy stat value to a JSON-safe type."""
    if isinstance(v, float) and math.isnan(v):
        return None
    if isinstance(v, (np.floating, np.integer)):
        val = v.item()
        return None if isinstance(val, float) and math.isnan(val) else val
    if hasattr(v, "strftime"):
        return str(v.date()) if hasattr(v, "date") else str(v)
    import pandas as pd
    if isinstance(v, pd.Timedelta):
        return str(v)
    return str(v)


def _activity_arrays(pf, n_days: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return (buy_count, sell_count, hold_count) arrays indexed by day.

    Uses np.asarray() on named record columns so the code works regardless of
    whether vectorbt returns numpy structured arrays or pandas DataFrames.
    """
    buy_arr  = np.zeros(n_days, dtype=int)
    sell_arr = np.zeros(n_days, dtype=int)
    hold_arr = np.zeros(n_days, dtype=int)

    # Buy / sell counts (side: 0=buy, 1=sell)
    orders = pf.orders.records
    if len(orders) > 0:
        idx_arr  = np.asarray(orders["idx"],  dtype=int)
        side_arr = np.asarray(orders["side"], dtype=int)
        np.add.at(buy_arr,  idx_arr[side_arr == 0], 1)
        np.add.at(sell_arr, idx_arr[side_arr == 1], 1)

    # Holding count: each position contributes 1 for every day it is open
    positions = pf.positions.records
    if len(positions) > 0:
        entry_arr  = np.asarray(positions["entry_idx"], dtype=int)
        exit_arr   = np.asarray(positions["exit_idx"],  dtype=int)
        status_arr = np.asarray(positions["status"],    dtype=int)
        for i in range(len(entry_arr)):
            start = entry_arr[i]
            end   = exit_arr[i] if status_arr[i] == 1 else n_days
            hold_arr[start:end] += 1

    return buy_arr, sell_arr, hold_arr


def _build_result(req: BacktestRequest) -> dict:
    pf, bm_close = compute_portfolio(req.model_dump())

    stats      = pf.stats()
    stats_dict = {k: _serialize(v) for k, v in stats.items()}

    pf_value = pf.value()
    n_days   = len(pf_value)
    base     = pf_value.iloc[0] or req.initial_capital

    buy_arr, sell_arr, hold_arr = _activity_arrays(pf, n_days)

    bm_stats_dict = None
    bm_norm       = None

    if bm_close is not None and not bm_close.isna().all():
        bm_pf    = vbt.Portfolio.from_holding(bm_close, init_cash=req.initial_capital)
        bm_stats = bm_pf.stats(settings=dict(freq="D"))
        bm_stats_dict = {k: _serialize(v) for k, v in bm_stats.items()}
        bm_value = bm_pf.value().reindex(pf_value.index).ffill()
        bm_base  = bm_value.iloc[0] or req.initial_capital
        bm_norm  = (bm_value / bm_base * 100).round(2)

    chart = []
    for i, (date, val) in enumerate(pf_value.items()):
        row: dict = {
            "date":       str(date.date()),
            "strategy":   round(val / base * 100, 2),
            "buy_count":  int(buy_arr[i]),
            "sell_count": int(sell_arr[i]),
            "hold_count": int(hold_arr[i]),
        }
        if bm_norm is not None:
            bv = bm_norm.get(date)
            row["benchmark"] = float(bv) if bv is not None and not math.isnan(float(bv)) else None
        chart.append(row)

    return {"stats": stats_dict, "benchmark_stats": bm_stats_dict, "chart": chart}


@router.post("/api/backtest")
async def run_backtest(req: BacktestRequest):
    """Run Phase III backtest with the given parameters and return stats + chart data."""
    try:
        loop   = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, lambda: _build_result(req))
        return result
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.error("[Backtest] Failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))
