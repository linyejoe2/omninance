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
            await execute_signals(strategy["_id"], settings)
        except Exception as exc:
            logger.error("[Scheduler] Strategy %s failed: %s", strategy["_id"], exc)

    logger.info("[Scheduler] Daily job finished")
    
def _compute_and_verify_signals():
    """執行計算並驗證訊號是否存在"""
    max_retries = 3
    retry_delay = 600  # 失敗後等 10 分鐘再試 (可能在等 Parquet 寫入)
    
    for i in range(max_retries):
        try:
            logger.info(f"[Compute and Verify Signals] Attempt {i+1} to compute signals...")
            
            with httpx.Client(base_url=_CHIP_TRACKER_URL, timeout=60.0) as ct:
                try:
                    resp = ct.post("/api/signals/compute", json=settings)
                    resp.raise_for_status()
                    signal_data = resp.json()
                except Exception as exc:
                    return [], [], {}, str(exc)
            # 假設傳入預設參數
            params = {"volume_multiplier": 1.5, "concentration_slope": 0.001, "back_test_period": 3}
            result = compute_signals(params)
            
            if result and len(result.get("buy", [])) >= 0: # 即使買入清單為空，只要有結果也算成功
                logger.info("[Compute and Verify Signals] Success! Signals generated.")
                return True
            else:
                logger.warning("[Compute and Verify Signals] Result empty or incomplete.")
                
        except Exception as e:
            logger.error(f"[Compute and Verify Signals] Attempt {i+1} failed: {e}")
            
        if i < max_retries - 1:
            time.sleep(retry_delay)
            
    # 如果三次都失敗，發送嚴重警告 (例如 Line 或 Slack)
    logger.critical("[Compute and Verify Signals] All attempts failed. Pipeline might be broken!")
    return False

def start_scheduler() -> None:
    scheduler.add_job(
        _run_daily_strategies,
        CronTrigger(day_of_week="mon-fri", hour=10, minute=16, timezone="Asia/Taipei"),
        id="daily_strategies",
        replace_existing=True,
        misfire_grace_time=300,
    )
    
    # 新增：下午定時計算並檢查訊號
    scheduler.add_job(
        _compute_and_verify_signals,
        CronTrigger(day_of_week="mon-fri", hour=15, minute=30, timezone="Asia/Taipei"),
        id="nightly_signal_check",
        replace_existing=True,
        misfire_grace_time=600,
    )
    scheduler.start()
    logger.info("[Scheduler] Started — daily job Mon-Fri 14:10 Asia/Taipei")


def stop_scheduler() -> None:
    scheduler.shutdown(wait=False)
    logger.info("[Scheduler] Stopped")
