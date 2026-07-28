"""
strategy_schedule.py — post-market strategy jobs, triggered by the ofelia
scheduler (see /ofelia.ini) instead of an in-process APScheduler:

  daily_strategies()   — Mon-Fri 10:04 Asia/Taipei — execute buy/sell
                                  for all active strategies' pending signals
  finalize_daily_settlement()  — Mon-Fri 15:00 Asia/Taipei — settle equity/PnL
                                  for today's executed daily logs
  nightly_signal_generate()  — Mon-Fri 15:30 Asia/Taipei — compute next-day
                                  signals and create Pending daily logs
"""
import logging

from src.core.date_time_util import get_date_tw, get_datetime_tw
from src.db import check_log_exists_for_post_market, get_activated_strategies
from src.modules.strategy import (
    create_pending_signal_log,
    execute_strategy,
    finalize_daily_settlement as _finalize_daily_settlement,
)
from src.service.chip_tracker import fetch_signals_with_retry

logger = logging.getLogger(__name__)


async def daily_strategies() -> dict:
    """Execute buy/sell orders for every active strategy's pending signal log."""
    logger.info(f"[Scheduler] Starting execute strategies... at {get_datetime_tw().isoformat()}")

    strategies = await get_activated_strategies()
    if not strategies:
        logger.info("[Scheduler] No active strategies to execute.")
        return {"total": 0, "executed": [], "failed": []}

    executed: list = []
    failed: list[dict] = []
    for strategy in strategies:
        try:
            logger.info(f"[Scheduler] Executing Strategy: {strategy.id}")
            await execute_strategy(strategy.id)
            executed.append(strategy.id)
        except Exception as exc:
            logger.error(f"[Scheduler] Strategy {strategy.id} execution failed: {exc}")
            failed.append({"strategy_id": strategy.id, "error": str(exc)})

    logger.info("[Scheduler] Morning execution job finished")
    return {"total": len(strategies), "executed": executed, "failed": failed}


async def finalize_daily_settlement() -> dict:
    """Settle today's executed daily log (equity/PnL) for every active strategy."""
    logger.info(f"[Scheduler] Starting finaliz daily settlement... at {get_datetime_tw().isoformat()}")

    strategies = await get_activated_strategies()
    if not strategies:
        logger.info("[Scheduler] No active strategies to execute.")
        return {"total": 0, "finalized": [], "failed": []}

    finalized: list = []
    failed: list[dict] = []
    for strategy in strategies:
        try:
            logger.info(f"[Scheduler] Finalize: {strategy.id}")
            await _finalize_daily_settlement(strategy.id)
            finalized.append(strategy.id)
        except Exception as exc:
            logger.error(f"[Scheduler] Strategy {strategy.id} finalization failed: {exc}")
            failed.append({"strategy_id": strategy.id, "error": str(exc)})

    logger.info("[Scheduler] Morning finalization job finished")
    return {"total": len(strategies), "finalized": finalized, "failed": failed}


async def nightly_signal_generate() -> dict:
    """盤後自動化任務：為所有 active 策略計算訊號並產生 Pending Log。"""
    logger.info(f"[Scheduler] Starting signal pipeline... at {get_datetime_tw().isoformat()}")
    strategies = await get_activated_strategies()

    if not strategies:
        logger.info("[Pipeline] No active strategies found. Skipping.")
        return {"total": 0, "created": [], "skipped": [], "failed": []}

    created: list[dict] = []
    skipped: list = []
    failed: list[dict] = []

    for strategy in strategies:
        logger.info(f"[Pipeline] Processing signals for Strategy: {strategy.id}")

        today = get_date_tw()
        is_already_computed = await check_log_exists_for_post_market(strategy.id, today)
        if is_already_computed:
            logger.info(f"Signal for strategy {strategy.id} already generated today ({today}). Skipping.")
            skipped.append(strategy.id)
            continue

        settings = {
            "volume_multiplier": strategy.volume_multiplier,
            "concentration_slope": strategy.concentration_slope,
            "back_test_period": 4,
        }

        buy_list, _, snapshot, error = fetch_signals_with_retry(settings)
        if error:
            logger.error(f"[Pipeline] Failed to get signals for {strategy.id}: {error}")
            failed.append({"strategy_id": strategy.id, "error": error})
            continue

        try:
            new_log = await create_pending_signal_log(strategy.id, buy_list, snapshot)
            if new_log:
                logger.info(f"[Pipeline] Successfully created Pending Log {new_log.id}")
                created.append({"strategy_id": strategy.id, "log_id": new_log.id})
            else:
                failed.append({"strategy_id": strategy.id, "error": "strategy not found"})
        except Exception as e:
            logger.critical(f"[Pipeline] DB Error while saving log for {strategy.id}: {e}")
            failed.append({"strategy_id": strategy.id, "error": str(e)})

    return {"total": len(strategies), "created": created, "skipped": skipped, "failed": failed}
