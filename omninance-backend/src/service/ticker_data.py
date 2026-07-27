"""
ticker_data.py — Ticker (daily OHLCV) refresh, ported from
omninance-chip-tracker/src/main.py::run_phase1 (CSV persistence replaced by
the MongoDB tickers collection).

TWSE/TPEx publish one new bar per trading day. The refresh:
  1. Groups symbols by their latest stored ticker date, so it only calls
     yfinance for symbols missing the most recently expected trading day —
     the hourly ofelia trigger is a cheap no-op outside that window.
  2. For each stale symbol, downloads just the missing range via yfinance
     (5y backfill for symbols with no history yet) and upserts new bars,
     keyed on (symbol, date) to match the unique index.
"""
import asyncio
import logging
from datetime import timedelta

import pandas as pd
from pymongo import UpdateOne

from src.core.date_time_util import get_last_trading_day_tw_string
from src.models import db as mongo_db
from src.models.Ticker import TickerModel
from src.service.stock_data import download_tickers

logger = logging.getLogger(__name__)

DEFAULT_BACKFILL_PERIOD = "5y"


def _rows_to_docs(symbol: str, df: pd.DataFrame) -> list[dict]:
    docs = []
    for idx, row in df.iterrows():
        model = TickerModel(
            symbol=symbol,
            date=pd.Timestamp(idx).strftime("%Y-%m-%d"),
            Open=float(row["Open"]),
            High=float(row["High"]),
            Low=float(row["Low"]),
            Close=float(row["Close"]),
            Volume=int(row["Volume"]),
        )
        # No by_alias: matches scripts/migrate_csv_to_mongo.py, which stores
        # lowercase field names (open/high/low/close/volume) in the tickers
        # collection, not the Open/High/Low/Close/Volume aliases.
        docs.append(model.model_dump(exclude={"id"}))
    return docs


def _fetch_new_bars(symbol: str, start: str | None) -> pd.DataFrame:
    """Blocking yfinance download — run in a thread."""
    if start is not None:
        return download_tickers(symbol, period=None, start=start)
    return download_tickers(symbol, period=DEFAULT_BACKFILL_PERIOD)


async def refresh_tickers() -> dict:
    """Bring the tickers collection up to the newest expected trading day."""
    db = mongo_db.get_db()

    stock_docs = await db["stock_list"].find({}, {"symbol": 1}).to_list(length=None)
    symbols = [doc["symbol"] for doc in stock_docs]
    if not symbols:
        return {"status": "no_symbols", "total": 0}

    cursor = db["tickers"].aggregate(
        [{"$group": {"_id": "$symbol", "last_date": {"$max": "$date"}}}]
    )
    last_dates = {row["_id"]: row["last_date"] for row in await cursor.to_list(length=None)}

    expected = get_last_trading_day_tw_string()
    stale_symbols = [s for s in symbols if last_dates.get(s, "") < expected]

    if not stale_symbols:
        logger.info(f"[Ticker] Up to date (>= {expected}); skipping refresh")
        return {"status": "up_to_date", "total": len(symbols), "expected_date": expected}

    updated = 0
    no_new_data = 0
    failed: list[str] = []
    new_bars = 0

    for symbol in stale_symbols:
        last_date = last_dates.get(symbol)
        # Incremental fetch starts the day after what we already have;
        # unseen symbols get a full backfill.
        start = None
        if last_date is not None:
            start = (pd.Timestamp(last_date) + timedelta(days=1)).strftime("%Y-%m-%d")

        df = await asyncio.to_thread(_fetch_new_bars, symbol, start)
        if df is None or df.empty:
            no_new_data += 1
            continue

        try:
            docs = _rows_to_docs(symbol, df)
            ops = [
                UpdateOne({"symbol": symbol, "date": d["date"]}, {"$set": d}, upsert=True)
                for d in docs
            ]
            result = await db["tickers"].bulk_write(ops, ordered=False)
            updated += 1
            new_bars += result.upserted_count + result.modified_count
        except Exception as exc:
            logger.warning(f"[Ticker] Upsert failed for {symbol}: {exc}")
            failed.append(symbol)

    summary = {
        "status": "refreshed",
        "total": len(symbols),
        "expected_date": expected,
        "updated": updated,
        "new_bars": new_bars,
        "no_new_data": no_new_data,
        "failed": failed,
    }
    logger.info(f"[Ticker] Refresh finished: {summary}")
    return summary
