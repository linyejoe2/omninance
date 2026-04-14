"""
scheduler.py — APScheduler for omninance-backend.

Runs Mon–Fri at 14:10 Asia/Taipei:
  1. Triggers the chip-tracker data pipeline (POST /api/trigger).
  2. For each active strategy, computes signals and executes orders.
"""
import logging
import os

import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from src.db import list_strategies
from src.routes.strategy import execute_signals

logger = logging.getLogger(__name__)

_CHIP_TRACKER_URL = os.environ.get("CHIP_TRACKER_URL", "http://chip-tracker:8000")

scheduler = AsyncIOScheduler(timezone="Asia/Taipei")


async def _run_daily_strategies() -> None:
    """Trigger pipeline, then run all active strategies."""
    logger.info("[Scheduler] Daily job started")

    # 1. Trigger chip-tracker pipeline and wait for it
    try:
        async with httpx.AsyncClient(base_url=_CHIP_TRACKER_URL, timeout=300.0) as ct:
            resp = await ct.post("/api/trigger")
            logger.info("[Scheduler] Pipeline trigger: %s", resp.status_code)
    except Exception as exc:
        logger.error("[Scheduler] Pipeline trigger failed: %s", exc)

    # 2. Execute each active strategy
    strategies = list_strategies(status="active")
    logger.info("[Scheduler] Executing %d active strategies", len(strategies))

    for strategy in strategies:
        settings = {
            "initial_capital":     strategy["initial_capital"],
            "partition":           strategy["partition"],
            "volume_multiplier":   strategy["volume_multiplier"],
            "concentration_slope": strategy["concentration_slope"],
            "atr_multiplier":      strategy["atr_multiplier"],
            "back_test_period":    strategy["back_test_period"],
        }
        try:
            execute_signals(strategy["_id"], settings)
        except Exception as exc:
            logger.error("[Scheduler] Strategy %s failed: %s", strategy["_id"], exc)

    logger.info("[Scheduler] Daily job finished")


def start_scheduler() -> None:
    scheduler.add_job(
        _run_daily_strategies,
        CronTrigger(day_of_week="mon-fri", hour=14, minute=10, timezone="Asia/Taipei"),
        id="daily_strategies",
        replace_existing=True,
        misfire_grace_time=300,
    )
    scheduler.start()
    logger.info("[Scheduler] Started — daily job Mon-Fri 14:10 Asia/Taipei")


def stop_scheduler() -> None:
    scheduler.shutdown(wait=False)
    logger.info("[Scheduler] Stopped")
