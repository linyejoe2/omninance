"""
strategy_schedule.py — strategy jobs, triggered by the ofelia scheduler
(see /ofelia.ini) via POST /api/schedules/{job}/trigger:

  daily-strategies           — Mon-Fri 10:04 Asia/Taipei — execute buy/sell
                               for today's SIGNAL_GENERATED daily logs
  finalize-daily-settlement  — Mon-Fri 15:00 Asia/Taipei — settle equity/PnL,
                               daily log → ENDED
  nightly-signal-generate    — Mon-Fri 15:30 Asia/Taipei — compute next-day
                               signals, create tomorrow's daily log

Each job fans out over active strategies, isolates per-strategy failures and
returns a summary dict that run_with_log() records in schedule_log.
"""
import logging
from typing import Awaitable, Callable

from src.db import get_session
from src.models.trading import Strategy
from src.modules.trading_engine import (
    execute_daily_strategy,
    finalize_daily_settlement as settle_strategy,
    generate_daily_signals,
)
from src.repositories import strategy_repo

logger = logging.getLogger(__name__)


async def _run_for_active_strategies(
    job_name: str, runner: Callable[[Strategy], Awaitable[dict]]
) -> dict:
    async with get_session() as session:
        strategies = await strategy_repo.list_active_strategies(session)

    if not strategies:
        logger.info(f"[{job_name}] No active strategies")
        return {"total": 0, "results": [], "failed": []}

    results: list[dict] = []
    failed: list[dict] = []
    for strategy in strategies:
        try:
            results.append(await runner(strategy))
        except Exception as exc:
            logger.error(f"[{job_name}] Strategy {strategy.id} failed: {exc}")
            failed.append({"strategy_id": strategy.id, "error": str(exc)})

    return {"total": len(strategies), "results": results, "failed": failed}


async def daily_strategies() -> dict:
    """09:00-13:30 盤中：執行所有策略今日的買賣。"""
    return await _run_for_active_strategies("Execute", execute_daily_strategy)


async def finalize_daily_settlement() -> dict:
    """15:00 盤後：結算所有策略今日的資產與損益。"""
    return await _run_for_active_strategies("Settle", settle_strategy)


async def nightly_signal_generate() -> dict:
    """15:30 盤後：為所有策略計算明日訊號並建立明日 Daily Log。"""
    return await _run_for_active_strategies("Signal", generate_daily_signals)
