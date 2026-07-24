"""
stock_list.py — StockList refresh via yfinance.

Refreshes market data (close, capitals, mkt_val, mkt_val_ratio, date) for every
symbol in the stock_list collection whose updated_at is older than the staleness
window, then recomputes rank per market by mkt_val. mkt_val_ratio is each
stock's share of its market's total capitalisation — TSE (上市, `.TW`) via
get_TSC_market_capital(), OTC (上櫃, `.TWO`) via get_OTC_market_capital().
The ofelia scheduler triggers this hourly; with the default 12-hour window the
data is effectively refreshed every half day.
"""
import asyncio
import logging
from datetime import timedelta, timezone

import yfinance as yf

from src.core.date_time_util import get_date_tw, get_datetime
from src.models import db as mongo_db
from src.service.stock_data import get_OTC_market_capital, get_TSC_market_capital

logger = logging.getLogger(__name__)

DEFAULT_MAX_AGE_HOURS = 12


def _market_of(symbol: str) -> str | None:
    """`.TWO` → OTC (上櫃), `.TW` → TSC (上市)."""
    if symbol.endswith(".TWO"):
        return "OTC"
    if symbol.endswith(".TW"):
        return "TSC"
    return None


def _fetch_market_totals() -> dict[str, int | None]:
    """Blocking TWSE/TPEx lookups — run in a thread. Totals in 百萬."""
    totals: dict[str, int | None] = {}
    try:
        totals["TSC"] = get_TSC_market_capital()
    except Exception as exc:
        logger.warning(f"[StockList] TSC market capital fetch failed: {exc}")
        totals["TSC"] = None
    try:
        totals["OTC"] = get_OTC_market_capital()
    except Exception as exc:
        logger.warning(f"[StockList] OTC market capital fetch failed: {exc}")
        totals["OTC"] = None
    return totals


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
            fields["mkt_val"] = round(float(fast_info.market_cap), 2)
            # # mkt_val 單位: 百萬
            # fields["mkt_val"] = round(float(fast_info.market_cap) / 1_000_000, 2)
        return fields
    except Exception as exc:
        logger.warning(f"[StockList] yfinance fetch failed for {symbol}: {exc}")
        return None


async def _recompute_ranks(db) -> int:
    """Re-rank stocks by mkt_val (descending) within each market; returns rows changed."""
    docs = await db["stock_list"].find({}, {"symbol": 1, "mkt_val": 1, "rank": 1}).to_list(length=None)

    groups: dict[str, list] = {"TSC": [], "OTC": []}
    for doc in docs:
        market = _market_of(doc["symbol"])
        if market is not None and doc.get("mkt_val") is not None:
            groups[market].append(doc)

    changed = 0
    for market_docs in groups.values():
        market_docs.sort(key=lambda d: d["mkt_val"], reverse=True)
        for rank, doc in enumerate(market_docs, start=1):
            if doc.get("rank") != rank:
                await db["stock_list"].update_one({"_id": doc["_id"]}, {"$set": {"rank": rank}})
                changed += 1
    return changed


async def refresh_stock_list(max_age_hours: int = DEFAULT_MAX_AGE_HOURS) -> dict:
    """Update stale stock_list documents; returns a summary of what happened."""
    db = mongo_db.get_db()
    now = get_datetime()
    cutoff = now - timedelta(hours=max_age_hours)

    docs = await db["stock_list"].find({}).to_list(length=None)

    stale_docs = []
    skipped = 0
    for doc in docs:
        updated_at = doc.get("updated_at")
        if updated_at is not None:
            # PyMongo returns naive datetimes in UTC
            if updated_at.tzinfo is None:
                updated_at = updated_at.replace(tzinfo=timezone.utc)
            if updated_at >= cutoff:
                skipped += 1
                continue
        stale_docs.append(doc)

    updated = 0
    failed: list[str] = []
    ranks_updated = 0

    if stale_docs:
        totals = await asyncio.to_thread(_fetch_market_totals)

        for doc in stale_docs:
            symbol = doc["symbol"]
            fields = await asyncio.to_thread(_fetch_symbol_info, symbol)
            if fields is None:
                failed.append(symbol)
                continue

            market = _market_of(symbol)
            total = totals.get(market) if market is not None else None
            if fields.get("mkt_val") and total:
                fields["mkt_val_ratio"] = round(fields["mkt_val"] / total, 5)

            fields["updated_at"] = now
            if doc.get("created_at") is None:
                fields["created_at"] = now

            await db["stock_list"].update_one({"_id": doc["_id"]}, {"$set": fields})
            updated += 1

        if updated:
            ranks_updated = await _recompute_ranks(db)

    summary = {
        "total": len(docs),
        "updated": updated,
        "skipped": skipped,
        "failed": failed,
        "ranks_updated": ranks_updated,
    }
    logger.info(f"[StockList] Refresh finished: {summary}")
    return summary
