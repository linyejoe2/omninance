"""
scheduler.py — APScheduler for omninance-backend.

Runs Mon–Fri at 14:10 Asia/Taipei:
  1. Triggers the chip-tracker data pipeline (POST /api/trigger).
  2. For each active strategy, computes signals and executes orders.
"""
import logging

from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import APIRouter

from src.db import get_activated_strategies
from src.service.chip_tracker import fetch_signals_with_retry
from src.modules.strategy import create_pending_signal_log, execute_strategy, finalize_daily_settlement
from src.core.date_time_util import get_datetime_tw, get_date_tw
from src.db import check_log_exists_for_post_market



logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone="Asia/Taipei")
router = APIRouter(tags=["scheduler"])


async def _run_daily_strategies() -> None:
    """Trigger pipeline, then run all active strategies."""
    logger.info(f"[Scheduler] Starting execute strategies... at {get_datetime_tw().isoformat()}")
    
    # 1. 取得所有啟動中的策略
    strategies = await get_activated_strategies()

    if not strategies:
        logger.info("[Scheduler] No active strategies to execute.")
        return

    # 2. 逐一執行策略 (State 3)
    # 這裡呼叫我們之前寫好的 execute_strategy_and_finalize
    for strategy in strategies:
        try:
            logger.info(f"[Scheduler] Executing Strategy: {strategy.id}")
            
            # 執行買賣動作、更新 Daily Log (從 Pending 轉為 Finished)
            await execute_strategy(strategy.id)
            
        except Exception as exc:
            logger.error(f"[Scheduler] Strategy {strategy.id} execution failed: {exc}")

    logger.info("[Scheduler] Morning execution job finished")
    
async def _run_finalize_daily_settlement() -> None:
    logger.info(f"[Scheduler] Starting finaliz daily settlement... at {get_datetime_tw().isoformat()}")
    
    # 1. 取得所有啟動中的策略
    strategies = await get_activated_strategies()

    if not strategies:
        logger.info("[Scheduler] No active strategies to execute.")
        return

    # 2. 逐一執行策略 (State 3)
    for strategy in strategies:
        try:
            logger.info(f"[Scheduler] Finalize: {strategy.id}")
            
            # 執行買賣動作、更新 Daily Log (從 Pending 轉為 Finished)
            await finalize_daily_settlement(strategy.id)
            
        except Exception as exc:
            logger.error(f"[Scheduler] Strategy {strategy.id} finalization failed: {exc}")

    logger.info("[Scheduler] Morning finalization job finished")
    
    
async def _run_daily_signal_pipeline():
    """
    盤後自動化任務：為所有 active 策略計算訊號並產生 Pending Log。
    """
    logger.info(f"[Scheduler] Starting signal pipeline... at {get_datetime_tw().isoformat()}")
    strategies = await get_activated_strategies()
        
    if not strategies:
        logger.info("[Pipeline] No active strategies found. Skipping.")
        return

    for strategy in strategies:
        logger.info(f"[Pipeline] Processing signals for Strategy: {strategy.id}")
        
        # 檢查今天是否已經生成過訊號 (以 compute_at 的日期為準)
        today = get_date_tw()
        
        # 這裡需要一個輔助函式來檢查今天是否已有紀錄
        is_already_computed = await check_log_exists_for_post_market(strategy.id, today)
        
        if is_already_computed:
            logger.info(f"Signal for strategy {strategy.id} already generated today ({today}). Skipping.")
            return None
        
        # 2. 準備 API 請求參數 (從 DB 讀取設定)
        settings = {
            "volume_multiplier": strategy.volume_multiplier,
            "concentration_slope": strategy.concentration_slope,
            "back_test_period": 4,
        }
        
        # 3. 獲取訊號 (含內建重試邏輯)
        buy_list, _, snapshot, error = fetch_signals_with_retry(settings)
        
        if error:
            logger.error(f"[Pipeline] Failed to get signals for {strategy.id}: {error}")
            # 這裡可以選擇是否要在 Daily Log 記一筆 error
            continue
            
        # 4. 呼叫之前寫好的函數：直接轉入 State 2 (Pending)
        try:
            new_log = await create_pending_signal_log(strategy.id, buy_list, snapshot)
            if new_log:
                logger.info(f"[Pipeline] Successfully created Pending Log {new_log.id}")
        except Exception as e:
            logger.critical(f"[Pipeline] DB Error while saving log for {strategy.id}: {e}")

def start_scheduler() -> None:
    scheduler.add_job(
        _run_daily_strategies,
        CronTrigger(day_of_week="mon-fri", hour=10, minute=16, timezone="Asia/Taipei"),
        id="daily_strategies",
        replace_existing=True,
        misfire_grace_time=300,
    )
    
    scheduler.add_job(
        _run_finalize_daily_settlement,
        CronTrigger(day_of_week="mon-fri", hour=15, minute=00, timezone="Asia/Taipei"),
        id="finalize_daily_settlement",
        replace_existing=True,
        misfire_grace_time=300,
    )
    
    # 新增：下午定時計算並檢查訊號
    scheduler.add_job(
        _run_daily_signal_pipeline,
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

@router.post("/trigger/{job_id}")
async def trigger_job(job_id: str):
    job = scheduler.get_job(job_id)
    if not job:
        return {"error": "Job not found"}
    
    # 立即觸發
    scheduler.modify_job(job_id, next_run_time=datetime.now())
    return {"status": f"Job {job_id} triggered manually"}