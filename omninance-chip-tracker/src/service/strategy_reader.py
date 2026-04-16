"""
strategy_reader.py — Read-only access to the shared strategy DB.

Chip-tracker mounts /app/database read-only so it can look up active
strategy settings without owning the DB schema.
"""
import sqlite3
import logging
from pathlib import Path

_DB_PATH = Path("/app/database/omninance.db")
logger = logging.getLogger(__name__)


def get_active_strategy_settings() -> dict | None:
    """
    Return the settings dict of the most recently created active strategy,
    or None if the DB is unavailable or no active strategies exist.
    """
    if not _DB_PATH.exists():
        return None
    try:
        conn = sqlite3.connect(f"file:{_DB_PATH}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute(
                """SELECT initial_capital, partition, volume_multiplier,
                          concentration_slope, atr_multiplier, back_test_period
                   FROM strategy
                   WHERE status = 'active'
                   ORDER BY create_at DESC
                   LIMIT 1"""
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()
    except Exception as exc:
        logger.warning("[StrategyReader] Could not read strategy DB: %s", exc)
        return None
