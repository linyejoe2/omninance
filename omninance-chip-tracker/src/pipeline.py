"""
pipeline.py — Data acquisition + signal generation pipeline.

Separate from the backtest (src/main.py::main).
Called by the scheduler and the manual trigger endpoint.
"""
import logging

from src.main import load_settings, load_symbols, update_stock_list, run_phase1, run_phase2
from src.service.signal_generator import generate_signals

logger = logging.getLogger(__name__)


def run_pipeline() -> dict:
    """
    Phase I  — OHLCV & holder data sync
    Phase II — Matrix engineering (price / volume / chip / ATR parquets)
    Signal   — Generate signals_YYYYMMDD.json for the next trading day

    Returns the signal dict produced by generate_signals().
    """
    logger.info("[Pipeline] Loading settings and symbol list")
    settings = load_settings()
    update_stock_list()
    symbols = load_symbols()
    logger.info("[Pipeline] %d symbol(s) loaded", len(symbols))

    run_phase1(symbols, settings)
    run_phase2(symbols)

    return generate_signals(settings)
