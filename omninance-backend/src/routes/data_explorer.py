"""
data_explorer.py — Read-only browsing of the chip-tracker's MongoDB data.

  GET /api/stock-list                    — all tracked symbols (stock_list collection)
  GET /api/stock-list/{symbol}/tickers   — OHLCV history for a symbol, oldest first
  GET /api/stock-list/{symbol}/holders   — holder concentration history for a symbol, oldest first
"""
import math
from typing import Any

from fastapi import APIRouter, HTTPException

from src.models import db as mongo_db
from src.models.Holder import HolderSummaryModel
from src.models.StockList import StockListModel
from src.models.Ticker import TickerModel

router = APIRouter(tags=["data-explorer"])


def _sanitize(value: Any) -> Any:
    """Recursively replace NaN/Infinity (invalid in JSON) with None."""
    if isinstance(value, float):
        return None if (math.isnan(value) or math.isinf(value)) else value
    if isinstance(value, dict):
        return {k: _sanitize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_sanitize(v) for v in value]
    return value


@router.get("/api/stock-list")
async def list_stock_list():
    cursor = mongo_db.get_db()["stock_list"].find({})
    docs = await cursor.to_list(length=None)
    return [_sanitize(StockListModel(**doc).model_dump(exclude={"id"})) for doc in docs]


@router.get("/api/stock-list/{symbol}/tickers")
async def get_stock_tickers(symbol: str):
    cursor = mongo_db.get_db()["tickers"].find({"symbol": symbol}).sort("date", 1)
    docs = await cursor.to_list(length=None)
    if not docs:
        raise HTTPException(status_code=404, detail=f"No ticker data for {symbol}")
    return [_sanitize(TickerModel(**doc).model_dump(exclude={"id"})) for doc in docs]


@router.get("/api/stock-list/{symbol}/holders")
async def get_stock_holders(symbol: str):
    cursor = mongo_db.get_db()["holders"].find({"symbol": symbol}).sort("date", 1)
    docs = await cursor.to_list(length=None)
    if not docs:
        raise HTTPException(status_code=404, detail=f"No holder data for {symbol}")
    return [_sanitize(HolderSummaryModel(**doc).model_dump(exclude={"id"})) for doc in docs]
