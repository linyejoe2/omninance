"""
pipeline.py — Data acquisition + signal generation pipeline.

Separate from the backtest (src/main.py::main).
Called by the scheduler and the manual trigger endpoint.
"""
import logging

from src.main import load_settings, load_symbols, update_stock_list, run_phase1, run_phase2
from src.service.signal_generator import generate_signals
from src.service.strategy_reader import get_active_strategy_settings

logger = logging.getLogger(__name__)


def run_pipeline() -> dict:
    """
    Phase I  — OHLCV & holder data sync
    Phase II — Matrix engineering (price / volume / chip / ATR parquets)
    Signal   — Generate signals_YYYYMMDD.json using active strategy settings
               (falls back to setting.json if no active strategy in DB)

    Returns the signal dict produced by generate_signals().
    """
    logger.info("[Pipeline] Loading settings and symbol list")
    file_settings = load_settings()
    update_stock_list()
    symbols = load_symbols()
    logger.info("[Pipeline] %d symbol(s) loaded", len(symbols))

    run_phase1(symbols, file_settings)
    run_phase2(symbols)

    strategy_settings = get_active_strategy_settings()
    if strategy_settings:
        # Merge: keep non-signal keys from file_settings, override signal params from DB
        settings = {**file_settings, **strategy_settings}
        logger.info("[Pipeline] Using active strategy settings from DB")
    else:
        settings = file_settings
        logger.info("[Pipeline] No active strategy in DB — using setting.json")

    return generate_signals(settings)
