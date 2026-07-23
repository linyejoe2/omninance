"""
stock_list.py — StockList refresh via yfinance.

Refreshes market data (close, capitals, mkt_val, date) for every symbol in the
stock_list collection whose updated_at is older than the staleness window.
The ofelia scheduler triggers this hourly; with the default 12-hour window the
data is effectively refreshed every half day.
"""
import asyncio
import logging
from datetime import timedelta, timezone

import yfinance as yf

from src.core.date_time_util import get_date_tw, get_datetime
from src.models import db as mongo_db

logger = logging.getLogger(__name__)

DEFAULT_MAX_AGE_HOURS = 12


def _fetch_symbol_info(symbol: str) -> dict | None:
    """Blocking yfinance lookup — run in a thread. Returns fields to $set, or None on failure."""
    try:
        fast_info = yf.Ticker(symbol).fast_info
        fields: dict = {"date": get_date_tw().isoformat()}
        if fast_info.last_price:
            fields["close"] = round(float(fast_info.last_price), 2)
        if fast_info.shares:
            fields["capitals"] = float(fast_info.shares)
        if fast_info.market_cap:
            fields["mkt_val"] = float(fast_info.market_cap)
            # # mkt_val 單位: 百萬
            # fields["mkt_val"] = round(float(fast_info.market_cap) / 1_000_000, 2)
        return fields
    except Exception as exc:
        logger.warning(f"[StockList] yfinance fetch failed for {symbol}: {exc}")
        return None


async def refresh_stock_list(max_age_hours: int = DEFAULT_MAX_AGE_HOURS) -> dict:
    """Update stale stock_list documents; returns a summary of what happened."""
    db = mongo_db.get_db()
    now = get_datetime()
    cutoff = now - timedelta(hours=max_age_hours)

    docs = await db["stock_list"].find({}).to_list(length=None)

    updated = 0
    skipped = 0
    failed: list[str] = []

    for doc in docs:
        updated_at = doc.get("updated_at")
        if updated_at is not None:
            # PyMongo returns naive datetimes in UTC
            if updated_at.tzinfo is None:
                updated_at = updated_at.replace(tzinfo=timezone.utc)
            if updated_at >= cutoff:
                skipped += 1
                continue

        symbol = doc["symbol"]
        fields = await asyncio.to_thread(_fetch_symbol_info, symbol)
        if fields is None:
            failed.append(symbol)
            continue

        fields["updated_at"] = now
        if doc.get("created_at") is None:
            fields["created_at"] = now

        await db["stock_list"].update_one({"_id": doc["_id"]}, {"$set": fields})
        updated += 1

    summary = {"total": len(docs), "updated": updated, "skipped": skipped, "failed": failed}
    logger.info(f"[StockList] Refresh finished: {summary}")
    return summary
